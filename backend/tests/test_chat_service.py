from collections.abc import AsyncIterator
from typing import Any

import pytest
from langgraph.types import Command


class FakeGraph:
    def __init__(self) -> None:
        self.input: object | None = None
        self.config: dict[str, Any] | None = None
        self.context: dict[str, Any] | None = None

    async def astream(self, **kwargs: Any) -> AsyncIterator[dict[str, object]]:
        self.input = kwargs["input"]
        self.config = kwargs["config"]
        self.context = kwargs["context"]
        yield {
            "type": "messages",
            "ns": [],
            "data": (
                {"type": "ai", "role": "assistant", "content": "Approved"},
                {"langgraph_node": "model", "lc_agent_name": "erp-agent"},
            ),
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
    assert graph.context is not None
    assert graph.context == {
        "user_id": "user-1",
        "username": "user-1",
        "agent_id": "motorparts-agent",
        "current_time": graph.context["current_time"],
        "retrieval_context": "",
    }
    assert events[-1] == {
        "event": "complete",
        "namespace": [],
        "data": {"thread_id": "thread-1"},
    }


class ParentAndSubagentGraph(FakeGraph):
    async def astream(self, **kwargs: Any) -> AsyncIterator[dict[str, object]]:
        self.input = kwargs["input"]
        self.config = kwargs["config"]
        self.context = kwargs["context"]
        yield {
            "type": "messages",
            "ns": ["tools:subagent-run"],
            "data": (
                {"type": "ai", "content": "internal result"},
                {
                    "langgraph_node": "model",
                    "lc_agent_name": "supplier_manager",
                    "checkpoint_ns": "tools:subagent-run",
                },
            ),
        }
        yield {
            "type": "messages",
            "ns": [],
            "data": (
                {"type": "ai", "content": "final answer"},
                {"langgraph_node": "model", "lc_agent_name": "erp-agent"},
            ),
        }


@pytest.mark.anyio
async def test_stream_preserves_parent_and_subagent_identity() -> None:
    from api_view.chat_service import ChatService

    graph = ParentAndSubagentGraph()
    service = ChatService(graph, None)

    events = [
        event
        async for event in service.stream(
            "create a supplier",
            "thread-1",
            "user-1",
        )
    ]
    chunks = [event for event in events if event["event"] == "message_chunk"]

    assert chunks[0]["namespace"] == ["tools:subagent-run"]
    assert chunks[0]["meta"]["lc_agent_name"] == "supplier_manager"
    assert chunks[0]["data"]["content"] == "internal result"
    assert chunks[1]["namespace"] == []
    assert chunks[1]["meta"]["lc_agent_name"] == "erp-agent"
    assert chunks[1]["data"]["content"] == "final answer"
