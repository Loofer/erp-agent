"""Graph streaming orchestration for the chat transport."""
import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from backend.logs.logging_config import setup_logging
from langgraph.types import Command

from agent.rag.hybrid_retriever import HybridRetriever, render_retrieval_context

from .chat_persistence import ConversationRepository, ThreadInfo

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
        conversations: ConversationRepository,
        *,
        graph_factory: Callable[[], Any] | None = None,
        agent_id: str = "motorparts-agent",
        rag_retriever: HybridRetriever | None = None,
    ) -> None:
        self._graph = graph
        self._graph_factory = graph_factory
        self._conversations = conversations
        self._agent_id = agent_id
        self._rag_retriever = rag_retriever

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
        # later checkpoints omit it — MAX() in list_threads() recovers the value.
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

        yield {"event": "conversation", "data": {"thread_id": thread_id}}

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
                        yield {
                            "event": "interrupt",
                            "namespace": ns_list,
                            "data": _interrupt_data(item, thread_id, ns_list),
                        }
                    if interrupts:
                        # Keep draining: LangGraph must finish unwinding for the
                        # checkpoint to record the pending interrupt.  Breaking
                        # early loses it and the resume replays the node instead.
                        continue
                    yield {
                        "event": "graph_state",
                        "namespace": ns_list,
                        "data": _state_data(graph_state),
                    }
                elif chunk_type == "messages":
                    # v2 "messages" payload is one (message_chunk, metadata)
                    # tuple — not a list of them.  Iterating it yields the
                    # message and the metadata as two separate events.
                    payload = chunk.get("data")
                    if isinstance(payload, (list, tuple)) and len(payload) == 2:
                        graph_message, msg_meta = payload
                    else:
                        graph_message, msg_meta = payload, {}
                    yield {
                        "event": "message_chunk",
                        "namespace": ns_list,
                        "meta": _message_meta(msg_meta),
                        "data": _message_data(graph_message, thread_id),
                    }
        except Exception:  # noqa: BLE001
            # 生产禁止直接repr(exc)对外暴露堆栈！
            _log.exception("Agent run failed for thread %s", thread_id)
            yield {
                "event": "error",
                "namespace": [],
                "meta": {},
                "data": {"thread_id": thread_id, "message": "Agent run exception"},
            }
            return

        if not interrupted:
            yield {"event": "complete", "namespace": [], "data": {"thread_id": thread_id}}

    async def list_threads(self, user_id: str) -> list[ThreadInfo]:
        """List the active agent's conversation threads for one user."""
        return await self._conversations.list_threads(user_id, self._agent_id)

    async def get_thread_messages(
        self, thread_id: str, user_id: str
    ) -> list[dict[str, object]]:
        """Return a flat, user-visible timeline from the checkpoint state.

        ``messages`` is the durable LangGraph state.  Keeping the projection
        here means history uses the same checkpoint source as normal chat,
        without a second event-log table.  Tool calls and ToolMessages are
        retained as independent timeline items instead of being discarded.
        """
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
            return []
        raw_messages = state.values.get("messages", [])
        return _serialize_timeline(raw_messages)

    def _get_graph(self) -> Any:
        if self._graph is None:
            if self._graph_factory is None:
                raise RuntimeError("ChatService requires a graph or graph_factory")
            self._graph = self._graph_factory()
        return self._graph


def _message_data(message: object, thread_id: str) -> object:
    model_dump = getattr(message, "model_dump", None)
    data = model_dump() if callable(model_dump) else message
    if isinstance(data, dict):
        return {**data, "thread_id": thread_id}
    return {"thread_id": thread_id, "message": data}


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
    restart, but it does retain root conversation messages, tool calls, and
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
                tool_call_positions[tool_call_id] = len(timeline)
                timeline.append(
                    {
                        "id": f"tool-call:{tool_call_id}",
                        "kind": "tool_call",
                        "content": "",
                        "actor_name": data.get("name"),
                        "tool_call_id": tool_call_id,
                        "tool_name": str(call.get("name") or "tool"),
                        "tool_args": call.get("args") or {},
                        "status": "running",
                    }
                )
            continue

        if msg_type == "tool":
            tool_call_id = str(data.get("tool_call_id") or message_id)
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
                    "tool_name": data.get("name"),
                    "status": status,
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
