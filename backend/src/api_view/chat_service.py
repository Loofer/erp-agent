"""Graph streaming orchestration for the chat transport."""
import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from backend.logs.logging_config import setup_logging
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agent.rag.hybrid_retriever import HybridRetriever, render_retrieval_context

from .chat_persistence import SessionEvent, SessionInfo, SessionRepository

setup_logging()
_log = logging.getLogger(__name__)

# Truncate initial_prompt so checkpoint metadata stays compact.
_INITIAL_PROMPT_MAX = 500

# HumanInTheLoopMiddleware decision types.  "respond" means the human answers
# *instead of* executing the tool, so it is the only decision that needs free
# text from the user; everything else is a button press.
_INPUT_DECISION = "respond"

_APPROVAL_HINT = "即将执行以下操作，请确认是否继续。"
_INPUT_HINT = "请补充所需信息以继续操作"


class ChatService:
    """Translate LangGraph stream events into frontend SSE events."""

    def __init__(
        self,
        graph: Any | None,
        sessions: SessionRepository | None,
        *,
        graph_factory: Callable[[], Any] | None = None,
        agent_id: str = "motorparts-agent",
        rag_retriever: HybridRetriever | None = None,
        debug: bool = False,
    ) -> None:
        self._graph = graph
        self._graph_factory = graph_factory
        self._sessions = sessions
        self._agent_id = agent_id
        self._rag_retriever = rag_retriever
        self._debug = debug

    async def stream(
        self,
        message: str | None,
        thread_id: str,
        user_id: str,
        resume_data: str | dict[str, object] | None = None,
        user_name: str | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        if resume_data is None and message is None:
            raise ValueError("message is required when resume_data is not provided")

        # user_id / agent_id injected into every checkpoint via config["metadata"].
        # initial_prompt is stored on the first run only; resume passes None so
        # later checkpoints omit it — MAX() in list_sessions() recovers the value.
        metadata: dict[str, object] = {
            "user_id": user_id,
            "agent_id": self._agent_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if message is not None:
            metadata["initial_prompt"] = message[:_INITIAL_PROMPT_MAX]

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "agent_id": self._agent_id,
            },
            "metadata": metadata,
        }
        context = {
            "user_id": user_id,
            "username": user_name or user_id,
            "agent_id": self._agent_id,
            "current_time": metadata["updated_at"],
            "retrieval_context": "",
        }

        if message is not None and self._rag_retriever is not None:
            try:
                retrieval = await asyncio.to_thread(self._rag_retriever.retrieve, message)
                context["retrieval_context"] = render_retrieval_context(retrieval.context)
            except Exception:  # noqa: BLE001
                _log.exception("RAG retrieval failed for thread %s", thread_id)

        turn_events = _SessionEventBuffer(
            thread_id=thread_id,
            turn_id=uuid.uuid4().hex,
            user_id=user_id,
            agent_id=self._agent_id,
        )
        if message is not None:
            turn_events.append_user_message(message)

        yield self._event("session", thread_id, data={})

        graph_input: object = (
            Command(resume=resume_data)
            if resume_data is not None
            else {"messages": [{"role": "user", "content": message}]}
        )

        interrupted = False
        # An interrupt raised inside a subagent is re-emitted at every enclosing
        # namespace as the graph unwinds, so the same Interrupt.id arrives more
        # than once.  Emit each one only on its first (innermost) sighting.
        seen_interrupts: set[str] = set()
        emitted_tool_calls: set[str] = set()
        try:
            graph = self._get_graph()
            async for chunk in graph.astream(
                input=graph_input,
                config=config,
                context=context,
                stream_mode=["messages", "values"],
                subgraphs=True,
                version="v2",
            ):
                # With version="v2" every chunk is a single dict shaped
                # {"type", "ns", "data", ...} — subgraphs=True puts the
                # namespace under "ns" rather than wrapping in a tuple.

                # logging.debug("[chat_service] threadId: %s Graph chunk: %r",thread_id, chunk)

                chunk_type = chunk.get("type")
                ns_list = list(chunk.get("ns") or ())
                if chunk_type == "values":
                    # v2 pops __interrupt__ out of the state into "interrupts".
                    graph_state = chunk.get("data", {})
                    interrupts = chunk.get("interrupts") or ()
                    for item in interrupts:
                        interrupt_id = getattr(item, "id", None)
                        if interrupt_id is not None:
                            if interrupt_id in seen_interrupts:
                                continue
                            seen_interrupts.add(interrupt_id)
                        interrupted = True
                        event = self._event(
                            "interrupt",
                            thread_id,
                            namespace=ns_list,
                            data=_interrupt_data(item, thread_id, ns_list),
                        )
                        turn_events.append_sse_event(event)
                        yield event
                    if interrupts:
                        # Keep draining: LangGraph must finish unwinding for the
                        # checkpoint to record the pending interrupt.  Breaking
                        # early loses it and the resume replays the node instead.
                        continue
                    for event in _semantic_calls_from_state(
                        graph_state,
                        thread_id,
                        ns_list,
                        emitted_tool_calls,
                    ):
                        sse_event = self._event(**event)
                        turn_events.append_sse_event(sse_event)
                        yield sse_event
                elif chunk_type == "messages":
                    # v2 "messages" payload is one (message_chunk, metadata)
                    # tuple — not a list of them.  Iterating it yields the
                    # message and the metadata as two separate events.
                    payload = chunk.get("data")
                    if isinstance(payload, (list, tuple)) and len(payload) == 2:
                        graph_message, msg_meta = payload
                    else:
                        graph_message, msg_meta = payload, {}
                    meta = _message_meta(msg_meta)
                    for event in _semantic_message_events(
                        graph_message,
                        thread_id,
                        ns_list,
                        meta,
                    ):
                        sse_event = self._event(**event)
                        turn_events.append_sse_event(sse_event)
                        yield sse_event
        except Exception:  # noqa: BLE001
            # 生产禁止直接repr(exc)对外暴露堆栈！
            _log.exception("Agent run failed for thread %s", thread_id)
            error_event = self._event(
                "error", thread_id, data={"message": "Agent run exception, try again later"}
            )
            turn_events.append_sse_event(error_event)
            await self._persist_turn_events(turn_events)
            yield error_event
            return

        if not interrupted:
            complete_event = self._event("complete", thread_id, data={})
            turn_events.append_sse_event(complete_event)
            await self._persist_turn_events(turn_events)
            yield complete_event
            return

        await self._persist_turn_events(turn_events)

    async def list_sessions(self, user_id: str) -> list[SessionInfo]:
        """List the active agent's sessions for one user."""
        if self._sessions is None:
            return []
        return await self._sessions.list_sessions(user_id, self._agent_id)

    async def get_session_messages(
        self, thread_id: str, user_id: str
    ) -> dict[str, object]:
        """Return the durable session timeline, with checkpoint fallback.

        The session event log includes child-graph text and tool activity that
        DeepAgents deliberately omits from the parent checkpoint state.
        """
        if self._sessions is not None:
            events = await self._sessions.get_session_events(
                thread_id, user_id, self._agent_id
            )
            if events:
                return {"messages": _serialize_session_timeline(events)}
            if not await self._sessions.owns_session(thread_id, user_id, self._agent_id):
                return {"messages": []}
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "agent_id": self._agent_id,
            }
        }
        graph = self._get_graph()
        state = await graph.aget_state(config)
        if state is None or not state.values:
            return {"messages": []}
        raw_messages = state.values.get("messages", [])
        return {"messages": _serialize_timeline(raw_messages)}

    async def delete_session(self, thread_id: str, user_id: str) -> bool:
        """Delete one owned session and all of its checkpoint namespaces."""
        if self._sessions is None:
            return False
        return await self._sessions.delete_session(thread_id, user_id, self._agent_id)

    async def _persist_turn_events(self, events: "_SessionEventBuffer") -> None:
        if self._sessions is None:
            return
        try:
            await self._sessions.append_events(events.events)
        except Exception:  # noqa: BLE001
            _log.exception("Session event persistence failed for thread %s", events.thread_id)

    def _get_graph(self) -> Any:
        if self._graph is None:
            if self._graph_factory is None:
                raise RuntimeError("ChatService requires a graph or graph_factory")
            self._graph = self._graph_factory()
        return self._graph

    def _event(
        self,
        event: str,
        thread_id: str,
        *,
        namespace: list[str] | None = None,
        agent_name: str | None = None,
        message_id: str | None = None,
        meta: dict[str, object] | None = None,
        data: dict[str, object],
        raw_message: object | None = None,
    ) -> dict[str, object]:
        """Build one stable, frontend-facing event envelope."""
        meta = meta or {}
        payload: dict[str, object] = {
            "event": event,
            "event_id": f"evt_{uuid.uuid4().hex}",
            "thread_id": thread_id,
            "namespace": namespace or [],
            "agent_name": agent_name or meta.get("lc_agent_name"),
            "message_id": message_id,
            "langgraph_node": meta.get("langgraph_node"),
            "langgraph_step": meta.get("langgraph_step"),
            "checkpoint_ns": meta.get("checkpoint_ns"),
            "data": data,
        }
        if self._debug:
            payload["debug"] = {
                "raw_metadata": meta,
                "raw_message": _debug_value(raw_message),
            }
        return {key: value for key, value in payload.items() if value is not None}


class _SessionEventBuffer:
    """Build a compact, append-only session event batch for one graph run."""

    def __init__(
        self, *, thread_id: str, turn_id: str, user_id: str, agent_id: str
    ) -> None:
        self.thread_id = thread_id
        self._turn_id = turn_id
        self._user_id = user_id
        self._agent_id = agent_id
        self._sequence = 0
        self.events: list[SessionEvent] = []
        self._text_event: SessionEvent | None = None

    def append_user_message(self, content: str) -> None:
        self._append("user_message", source="user", payload={"content": content})

    def append_sse_event(self, event: dict[str, object]) -> None:
        event_type = _string(event.get("event"))
        if event_type == "message_chunk":
            self._append_text(event)
            return
        if event_type == "session":
            return
        self._text_event = None
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if event_type == "agent_routing":
            self._append("agent_routing", event=event, payload=data)
        elif event_type == "tool_call_start":
            self._append("tool_call_start", event=event, payload=data)
        elif event_type == "tool_call_end":
            self._append("tool_call_end", event=event, payload=data)
        elif event_type == "interrupt":
            self._append("interrupt", event=event, payload=data)
        elif event_type == "complete":
            self._append("turn_completed", event=event, payload=data)
        elif event_type == "error":
            self._append("turn_error", event=event, payload=data)

    def _append_text(self, event: dict[str, object]) -> None:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        content = _string(data.get("content"))
        if not content:
            return
        source = _event_source(event)
        agent_name = _string(event.get("agent_name"))
        namespace = _event_namespace(event)
        if (
            self._text_event is not None
            and self._text_event["source"] == source
            and self._text_event["agent_name"] == agent_name
            and self._text_event["namespace"] == namespace
            and self._text_event["message_id"] == _string(event.get("message_id"))
        ):
            existing = self._text_event["payload"].get("content", "")
            self._text_event["payload"]["content"] = f"{existing}{content}"
            return
        self._text_event = self._append(
            "assistant_text",
            event=event,
            payload={"content": content},
        )

    def _append(
        self,
        event_type: str,
        *,
        source: str | None = None,
        event: dict[str, object] | None = None,
        payload: dict[str, object],
    ) -> SessionEvent:
        self._sequence += 1
        stored: SessionEvent = {
            "event_id": (_string(event.get("event_id")) if event else None)
            or uuid.uuid4().hex,
            "thread_id": self.thread_id,
            "turn_id": self._turn_id,
            "sequence": self._sequence,
            "event_type": event_type,
            "user_id": self._user_id,
            "agent_id": self._agent_id,
            "source": source or _event_source(event or {}),
            "namespace": _event_namespace(event or {}),
            "agent_name": _string((event or {}).get("agent_name")),
            "message_id": _string((event or {}).get("message_id")),
            "tool_call_id": _string(payload.get("tool_call_id")),
            "tool_name": _string(payload.get("tool_name")),
            "payload": dict(payload),
            "created_at": datetime.now(UTC),
        }
        self.events.append(stored)
        return stored


def _event_namespace(event: dict[str, object]) -> list[str]:
    namespace = event.get("namespace")
    return [item for item in namespace if isinstance(item, str)] if isinstance(namespace, list) else []


def _event_source(event: dict[str, object]) -> str:
    agent_name = _string(event.get("agent_name"))
    if agent_name:
        return agent_name
    for item in _event_namespace(event):
        if item.startswith("tools:"):
            return item.removeprefix("tools:")
    return "main"


def _message_data(message: object, thread_id: str) -> object:
    model_dump = getattr(message, "model_dump", None)
    data = model_dump() if callable(model_dump) else message
    if isinstance(data, dict):
        return {**data, "thread_id": thread_id}
    return {"thread_id": thread_id, "message": data}


def _semantic_message_events(
    message: object,
    thread_id: str,
    namespace: list[str],
    meta: dict[str, object],
) -> list[dict[str, object]]:
    """Project one streamed LangChain message into user-facing event types.

    Tool starts are emitted from completed state snapshots because streamed tool
    chunks often contain only partial JSON. Tool results, by contrast, arrive
    as complete ToolMessages and can be emitted immediately.
    """
    data = _message_dict(message)
    message_id = _string(data.get("id"))
    agent_name = _string(data.get("name")) or _string(meta.get("lc_agent_name"))

    if isinstance(message, AIMessage) or _is_test_message(data, "ai"):
        content = _content_text(data.get("content"))
        if content:
            return [
                {
                    "event": "message_chunk",
                    "thread_id": thread_id,
                    "namespace": namespace,
                    "agent_name": agent_name,
                    "message_id": message_id,
                    "meta": meta,
                    "data": {"content": content},
                    "raw_message": message,
                }
            ]
        return []

    if isinstance(message, ToolMessage) or _is_test_message(data, "tool"):
        tool_name = _string(data.get("name"))
        # ToolMessage.name is the tool name, not the agent that invoked it.
        agent_name = _string(meta.get("lc_agent_name"))
        # A task result is an internal summary passed back to the parent agent.
        if tool_name == "task":
            return []
        events = [
            {
                "event": "tool_call_end",
                "thread_id": thread_id,
                "namespace": namespace,
                "agent_name": agent_name,
                "message_id": message_id,
                "meta": meta,
                "data": {
                    "tool_call_id": _string(data.get("tool_call_id")),
                    "tool_name": tool_name or "tool",
                    "result": _content_text(data.get("content")),
                    "tool_status": _string(data.get("status")),
                },
                "raw_message": message,
            }
        ]
        return events
    # HumanMessage has no user-visible streaming projection. It is retained in
    # checkpoint history and is handled by the HTTP history serializer.
    if isinstance(message, HumanMessage) or _is_test_message(data, "human"):
        return []
    return []


def _semantic_calls_from_state(
    state: object,
    thread_id: str,
    namespace: list[str],
    emitted_tool_calls: set[str],
) -> list[dict[str, object]]:
    """Emit one complete start or routing event for each newly seen tool call."""
    if not isinstance(state, dict):
        return []
    messages = state.get("messages")
    if not isinstance(messages, list):
        return []

    events: list[dict[str, object]] = []
    for message in messages:

        message_data = _message_dict(message)
        if not isinstance(message, AIMessage) and not _is_test_message(message_data, "ai"):
            continue
        message_id = _string(message_data.get("id"))
        agent_name = _string(message_data.get("name"))
        for index, call in enumerate(message_data.get("tool_calls") or []):
            if not isinstance(call, dict):
                continue
            tool_call_id = _string(call.get("id"))
            tool_name = _string(call.get("name"))
            if not tool_call_id or not tool_name or tool_call_id in emitted_tool_calls:
                continue
            emitted_tool_calls.add(tool_call_id)
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            base = {
                "thread_id": thread_id,
                "namespace": namespace,
                "agent_name": agent_name,
                "message_id": message_id,
                "meta": {},
                "raw_message": message,
            }
            if tool_name == "task":
                events.append(
                    {
                        **base,
                        "event": "agent_routing",
                        "data": {
                            "tool_call_id": tool_call_id,
                            "tool_call_index": index,
                            "subagent_type": _string(args.get("subagent_type")),
                            "description": _string(args.get("description")),
                        },
                    }
                )
            else:
                events.append(
                    {
                        **base,
                        "event": "tool_call_start",
                        "data": {
                            "tool_call_id": tool_call_id,
                            "tool_call_index": index,
                            "tool_name": tool_name,
                            "args": args,
                        },
                    }
                )
    return events


def _message_dict(message: object) -> dict[str, object]:
    model_dump = getattr(message, "model_dump", None)
    data = model_dump() if callable(model_dump) else message
    return data if isinstance(data, dict) else {}


def _is_test_message(data: dict[str, object], message_type: str) -> bool:
    """Accept the dict-shaped fake messages used by focused service tests."""
    return data.get("type") == message_type


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _debug_value(value: object | None) -> object | None:
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    return model_dump() if callable(model_dump) else value


# Only the metadata the UI needs.  The raw dict also carries lc_versions,
# langgraph_path, ls_* tracing keys and similar noise.
_META_KEYS = ("langgraph_node", "langgraph_step", "lc_agent_name", "checkpoint_ns")


def _message_meta(meta: object) -> dict[str, object]:
    """Project LangGraph message metadata down to the UI-relevant keys."""
    if not isinstance(meta, dict):
        return {}
    return {key: meta[key] for key in _META_KEYS if meta.get(key) is not None}


def _state_data(state: object) -> dict[str, object]:
    """Summarise a values chunk — the full message list is streamed separately."""
    if not isinstance(state, dict):
        return {}
    messages = state.get("messages")
    return {
        "message_count": len(messages) if isinstance(messages, list) else 0,
        "todos": state.get("todos") or [],
    }


def _interrupt_data(
    item: object, thread_id: str, namespace: list[str]
) -> dict[str, object]:
    """Translate one LangGraph Interrupt into the frontend interrupt contract.

    HumanInTheLoopMiddleware interrupts carry a HITLRequest:
        {"action_requests": [{"name", "args", "description"}],
         "review_configs": [{"action_name", "allowed_decisions"}]}
    and expect ``Command(resume={"decisions": [...]})`` to continue.  The
    allowed decisions come straight from each tool's review config, so the UI
    can render exactly the buttons the graph will accept. Native tool-input
    interrupts carry ``{"kind": "tool_input", ...}`` and resume with raw text.
    """
    raw_value = getattr(item, "value", item)
    interrupt_id = getattr(item, "id", None)

    actions: list[dict[str, object]] = []
    decisions: list[str] = []
    is_tool_input = (
        isinstance(raw_value, dict) and raw_value.get("kind") == "tool_input"
    )
    if isinstance(raw_value, dict):
        decisions_by_action: dict[str, list[str]] = {}
        for config in raw_value.get("review_configs") or []:
            if isinstance(config, dict):
                allowed = config.get("allowed_decisions")
                if isinstance(allowed, list):
                    decisions_by_action[str(config.get("action_name"))] = [
                        str(decision) for decision in allowed
                    ]
        for request in raw_value.get("action_requests") or []:
            if not isinstance(request, dict):
                continue
            name = str(request.get("name", ""))
            allowed = decisions_by_action.get(name, [])
            actions.append(
                {
                    "name": name,
                    "args": request.get("args") or {},
                    "description": request.get("description") or "",
                    "allowed_decisions": allowed,
                }
            )
            decisions.extend(d for d in allowed if d not in decisions)

    # Native tool-input interrupts resume with the input value itself. HITL
    # middleware input interrupts retain their decisions/respond envelope.
    is_input = is_tool_input or decisions == [_INPUT_DECISION]
    interrupt_mode = "input" if is_input else "approval"
    resume_mode = "value" if is_tool_input else "decisions"
    if is_tool_input:
        hint = str(raw_value.get("message") or _INPUT_HINT)
    else:
        hint = _INPUT_HINT if is_input else _APPROVAL_HINT

    return {
        "thread_id": thread_id,
        "interrupt_id": interrupt_id,
        "namespace": namespace,
        "interrupt_mode": interrupt_mode,
        "resume_mode": resume_mode,
        "allowed_decisions": decisions,
        "actions": actions,
        "hint": hint,
        # Raw value kept for debugging / non-HITL interrupts the UI can render
        # generically.  Not used to build the resume payload.
        "value": raw_value if isinstance(raw_value, (dict, list, str)) else str(raw_value),
    }


def _serialize_timeline(messages: object) -> list[dict[str, object]]:
    """Project checkpoint messages into chronological flat timeline entries.

    System messages are agent configuration and remain private.  The public
    message state does not reliably retain every inner subgraph token after a
    restart, but it does retain root session messages, tool calls, and
    tool results.  Live SSE continues to display subagent output as it arrives.
    """
    if not isinstance(messages, list):
        return []

    timeline: list[dict[str, object]] = []
    tool_call_positions: dict[str, int] = {}
    for message in messages:
        model_dump = getattr(message, "model_dump", None)
        data: dict = (
            model_dump() if callable(model_dump)
            else (message if isinstance(message, dict) else {})
        )
        msg_type = data.get("type", "")
        message_id = str(data.get("id") or "")

        if msg_type == "human":
            timeline.append(
                {
                    "id": message_id,
                    "kind": "user",
                    "role": "user",
                    "content": _content_text(data.get("content", "")),
                    "actor_name": data.get("name"),
                }
            )
            continue

        if msg_type == "ai":
            content = _content_text(data.get("content", ""))
            if content:
                timeline.append(
                    {
                        "id": message_id,
                        "kind": "assistant",
                        "role": "assistant",
                        "content": content,
                        "actor_name": data.get("name"),
                    }
                )
            for position, call in enumerate(data.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                tool_call_id = str(call.get("id") or f"{message_id}:{position}")
                tool_name = str(call.get("name") or "tool")
                args = call.get("args") or {}
                if tool_name == "task":
                    timeline.append(
                        {
                            "id": f"routing:{tool_call_id}",
                            "kind": "agent_routing",
                            "content": "",
                            "actor_name": data.get("name"),
                            "tool_call_id": tool_call_id,
                            "subagent_type": args.get("subagent_type")
                            if isinstance(args, dict)
                            else None,
                            "description": args.get("description")
                            if isinstance(args, dict)
                            else None,
                        }
                    )
                    continue
                tool_call_positions[tool_call_id] = len(timeline)
                timeline.append(
                    {
                        "id": f"tool-call:{tool_call_id}",
                        "kind": "tool_call",
                        "content": "",
                        "actor_name": data.get("name"),
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "tool_args": args,
                    }
                )
            continue

        if msg_type == "tool":
            tool_call_id = str(data.get("tool_call_id") or message_id)
            tool_name = str(data.get("name") or "tool")
            if tool_name == "task":
                continue
            status = "error" if data.get("status") == "error" else "success"
            call_position = tool_call_positions.get(tool_call_id)
            if call_position is not None:
                timeline[call_position]["status"] = status
            timeline.append(
                {
                    "id": message_id or f"tool-result:{tool_call_id}",
                    "kind": "tool_result",
                    "content": _content_text(data.get("content", "")),
                    "actor_name": data.get("name"),
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "status": status,
                }
            )

    return timeline


def _serialize_session_timeline(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """Project append-only session events into the existing frontend timeline."""
    timeline: list[dict[str, object]] = []
    tool_calls: dict[str, int] = {}
    for event in events:
        event_type = _string(event.get("event_type"))
        event_id = _string(event.get("event_id")) or uuid.uuid4().hex
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        actor_name = _string(event.get("agent_name")) or _string(event.get("source"))
        namespace = event.get("namespace") if isinstance(event.get("namespace"), list) else []
        if event_type == "user_message":
            timeline.append(
                {
                    "id": event_id,
                    "kind": "user",
                    "role": "user",
                    "content": _content_text(payload.get("content", "")),
                }
            )
        elif event_type == "assistant_text":
            timeline.append(
                {
                    "id": event_id,
                    "kind": "assistant",
                    "role": "assistant",
                    "content": _content_text(payload.get("content", "")),
                    "actor_name": actor_name,
                    "namespace": namespace,
                }
            )
        elif event_type == "agent_routing":
            timeline.append(
                {
                    "id": event_id,
                    "kind": "agent_routing",
                    "content": "",
                    "actor_name": actor_name,
                    "tool_call_id": _string(payload.get("tool_call_id")),
                    "subagent_type": _string(payload.get("subagent_type")),
                    "description": _string(payload.get("description")),
                    "namespace": namespace,
                }
            )
        elif event_type == "tool_call_start":
            tool_call_id = _string(payload.get("tool_call_id"))
            entry = {
                "id": f"tool-call:{tool_call_id or event_id}",
                "kind": "tool_call",
                "content": "",
                "actor_name": actor_name,
                "tool_call_id": tool_call_id,
                "tool_name": _string(payload.get("tool_name")) or "tool",
                "tool_args": payload.get("args") if isinstance(payload.get("args"), dict) else {},
                "status": "running",
                "namespace": namespace,
            }
            if tool_call_id:
                tool_calls[tool_call_id] = len(timeline)
            timeline.append(entry)
        elif event_type == "tool_call_end":
            tool_call_id = _string(payload.get("tool_call_id"))
            status = "error" if payload.get("tool_status") == "error" else "success"
            call_index = tool_calls.get(tool_call_id or "")
            if call_index is not None:
                timeline[call_index]["status"] = status
            timeline.append(
                {
                    "id": _string(event.get("message_id")) or f"tool-result:{tool_call_id or event_id}",
                    "kind": "tool_result",
                    "content": _content_text(payload.get("result", "")),
                    "actor_name": actor_name,
                    "tool_call_id": tool_call_id,
                    "tool_name": _string(payload.get("tool_name")) or "tool",
                    "status": status,
                    "namespace": namespace,
                }
            )
    return timeline


def _content_text(content: object) -> str:
    """Extract text from either standard or multimodal LangChain content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content) if content is not None else ""


def _serialize_message(message: object) -> "dict[str, object] | None":
    """Backward-compatible helper for callers expecting one visible message."""
    model_dump = getattr(message, "model_dump", None)
    data: dict = (
        model_dump() if callable(model_dump)
        else (message if isinstance(message, dict) else {})
    )

    msg_type = data.get("type", "")
    if msg_type == "human":
        role = "user"
    elif msg_type == "ai":
        role = "assistant"
    else:
        return None  # tool / system / function messages — skip

    content = _content_text(data.get("content", ""))

    # Skip AI messages that carry only tool_calls and have no visible text
    if not content and role == "assistant":
        return None

    return {"id": data.get("id") or "", "role": role, "content": content}
