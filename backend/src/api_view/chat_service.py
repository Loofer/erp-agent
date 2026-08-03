"""Graph streaming orchestration for the chat transport."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command

from .chat_persistence import ConversationRepository, ThreadInfo

# Truncate initial_prompt so checkpoint metadata stays compact.
_INITIAL_PROMPT_MAX = 500


class ChatService:
    """Translate LangGraph stream events into frontend SSE events."""

    def __init__(
        self,
        graph: Any | None,
        conversations: ConversationRepository,
        *,
        graph_factory: Callable[[], Any] | None = None,
        agent_id: str = "motorparts-agent",
    ) -> None:
        self._graph = graph
        self._graph_factory = graph_factory
        self._conversations = conversations
        self._agent_id = agent_id

    async def stream(
        self,
        message: str | None,
        thread_id: str,
        user_id: str,
        resume_data: dict[str, object] | None = None,
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
            "username": user_id,
            "agent_id": self._agent_id,
        }

        yield {"event": "conversation", "data": {"thread_id": thread_id}}

        graph_input: object = (
            Command(resume=resume_data)
            if resume_data is not None
            else {"messages": [{"role": "user", "content": message}]}
        )

        interrupted = False
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
                chunk_type = chunk.get("type")
                if chunk_type == "values":
                    # LangGraph v2 streaming: payload is under "data", not "values".
                    graph_state = chunk.get("data", {})
                    if "__interrupt__" in graph_state:
                        interrupted = True
                        yield {
                            "event": "interrupt",
                            "data": {
                                "thread_id": thread_id,
                                "resume_data": graph_state["__interrupt__"],
                                "hint": "Waiting for a human decision or supplemental data.",
                            },
                        }
                        break
                    yield {"event": "graph_state", "data": graph_state}
                elif chunk_type == "messages":
                    # LangGraph v2 streaming: payload is under "data", not "messages".
                    # Each item is a (message_chunk, metadata) tuple.
                    for item in chunk.get("data", []):
                        graph_message = item[0] if isinstance(item, (list, tuple)) else item
                        yield {
                            "event": "message_chunk",
                            "data": _message_data(graph_message, thread_id),
                        }
                elif chunk_type in {"node_start", "node_end"}:
                    yield {"event": chunk_type, "data": chunk}
        except Exception as exc:  # noqa: BLE001 - translate graph failures to SSE.
            yield {"event": "error", "data": {"error": repr(exc)}}
            return

        if not interrupted:
            yield {"event": "complete", "data": {"thread_id": thread_id}}

    async def list_threads(self, user_id: str) -> list[ThreadInfo]:
        """List the active agent's conversation threads for one user."""
        return await self._conversations.list_threads(user_id, self._agent_id)

    async def get_thread_messages(
        self, thread_id: str, user_id: str
    ) -> list[dict[str, object]]:
        """Return the human/AI messages stored in a thread's checkpoint state."""
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
        return [s for m in raw_messages if (s := _serialize_message(m)) is not None]

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


def _serialize_message(message: object) -> "dict[str, object] | None":
    """Serialize a LangChain message to a simple {id, role, content} dict.

    Returns None for messages that should not be surfaced in the UI
    (tool messages, system messages, empty AI tool-call stubs).
    """
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

    content = data.get("content", "")
    if isinstance(content, list):
        # ContentBlock list: extract text parts only
        content = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )

    # Skip AI messages that carry only tool_calls and have no visible text
    if not content and role == "assistant":
        return None

    return {"id": data.get("id") or "", "role": role, "content": content}
