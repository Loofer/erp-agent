from collections.abc import AsyncIterator
from typing import Any

import pytest
from langgraph.types import Command


class FakeGraph:
    def __init__(self) -> None:
        self.input: object | None = None
        self.config: dict[str, Any] | None = None

    async def astream(self, **kwargs: Any) -> AsyncIterator[dict[str, object]]:
        self.input = kwargs["input"]
        self.config = kwargs["config"]
        yield {
            "type": "messages",
            "messages": [
                {"type": "ai", "role": "assistant", "content": "Approved"}
            ],
        }


@pytest.mark.anyio
async def test_resume_stream_uses_command_and_thread_configuration() -> None:
    from api_view.chat_service import ChatService

    graph = FakeGraph()
    service = ChatService(graph, None)  # conversations not used during stream()

    events = [
        event
        async for event in service.stream(
            None,
            "thread-1",
            "user-1",
            {"supplement": "ABC"},
        )
    ]

    assert isinstance(graph.input, Command)
    # configurable drives LangGraph thread routing
    assert graph.config["configurable"] == {
        "thread_id": "thread-1",
        "user_id": "user-1",
        "agent_id": "motorparts-agent",
    }
    # metadata is persisted into every checkpoint for history queries
    assert graph.config["metadata"]["user_id"] == "user-1"
    assert graph.config["metadata"]["agent_id"] == "motorparts-agent"
    assert events[-1] == {"event": "complete", "data": {"thread_id": "thread-1"}}
