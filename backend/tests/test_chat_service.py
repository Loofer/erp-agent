from collections.abc import AsyncIterator
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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
                {"langgraph_node": "model", "lc_agent_name": "motorparts-agent"},
            ),
        }


@pytest.mark.anyio
async def test_resume_stream_uses_command_and_thread_configuration() -> None:
    from api_view.chat_service import ChatService

    graph = FakeGraph()
    service = ChatService(graph, None)  # session storage is not used in this test

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
    assert events[-1]["event"] == "complete"
    assert events[-1]["thread_id"] == "thread-1"
    assert events[-1]["namespace"] == []
    assert events[-1]["data"] == {}
    assert events[-1]["event_id"].startswith("evt_")


@pytest.mark.anyio
async def test_native_tool_input_resumes_with_the_raw_user_value() -> None:
    from api_view.chat_service import ChatService

    graph = FakeGraph()
    service = ChatService(graph, None)

    await _collect(service.stream(None, "thread-1", "user-1", "创建人是 7"))

    assert isinstance(graph.input, Command)
    assert graph.input.resume == "创建人是 7"


def test_native_tool_interrupt_is_exposed_as_value_input() -> None:
    from api_view.chat_service import _interrupt_data

    data = _interrupt_data(
        {
            "kind": "tool_input",
            "tool_name": "request_order_info",
            "message": "还缺 createdBy",
            "missing_fields": ["createdBy"],
        },
        "thread-1",
        ["tools:order"],
    )

    assert data["interrupt_mode"] == "input"
    assert data["resume_mode"] == "value"
    assert data["hint"] == "还缺 createdBy"


async def _collect(events: AsyncIterator[dict[str, object]]) -> list[dict[str, object]]:
    return [event async for event in events]


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
                {"langgraph_node": "model", "lc_agent_name": "motorparts-agent"},
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
    assert chunks[0]["agent_name"] == "supplier_manager"
    assert chunks[0]["data"]["content"] == "internal result"
    assert chunks[1]["namespace"] == []
    assert chunks[1]["agent_name"] == "motorparts-agent"
    assert chunks[1]["data"]["content"] == "final answer"


class RecordingSessionRepository:
    def __init__(self) -> None:
        self.batches: list[list[dict[str, object]]] = []

    async def append_events(self, events: list[dict[str, object]]) -> None:
        self.batches.append(events)

    async def get_session_events(self, *_: object) -> list[dict[str, object]]:
        return []


@pytest.mark.anyio
async def test_session_log_retains_subagent_text_after_stream_completion() -> None:
    from api_view.chat_service import ChatService

    sessions = RecordingSessionRepository()
    service = ChatService(ParentAndSubagentGraph(), sessions)

    events = [
        event
        async for event in service.stream("create a supplier", "thread-1", "user-1")
    ]

    assert events[0]["event"] == "session"
    stored = sessions.batches[0]
    assert [event["event_type"] for event in stored] == [
        "user_message",
        "assistant_text",
        "assistant_text",
        "turn_completed",
    ]
    assert stored[1]["source"] == "supplier_manager"
    assert stored[1]["namespace"] == ["tools:subagent-run"]
    assert stored[1]["payload"] == {"content": "internal result"}
    assert stored[2]["source"] == "motorparts-agent"


class SubagentToolGraph(FakeGraph):
    async def astream(self, **kwargs: Any) -> AsyncIterator[dict[str, object]]:
        self.input = kwargs["input"]
        self.config = kwargs["config"]
        self.context = kwargs["context"]
        yield {
            "type": "values",
            "ns": ["tools:procurement_analyst"],
            "data": {
                "messages": [
                    AIMessage(
                        content="",
                        id="subagent-ai",
                        name="procurement_analyst",
                        tool_calls=[
                            {
                                "id": "search-1",
                                "name": "part_search",
                                "args": {"keyword": "FR7DC+"},
                            }
                        ],
                    )
                ]
            },
        }
        yield {
            "type": "messages",
            "ns": ["tools:procurement_analyst"],
            "data": (
                ToolMessage(
                    content='{"items": []}',
                    id="search-result",
                    tool_call_id="search-1",
                    name="part_search",
                ),
                {"lc_agent_name": "procurement_analyst"},
            ),
        }


@pytest.mark.anyio
async def test_session_log_links_subagent_tool_events_by_native_tool_call_id() -> None:
    from api_view.chat_service import ChatService

    sessions = RecordingSessionRepository()
    service = ChatService(SubagentToolGraph(), sessions)
    await _collect(service.stream("find a part", "thread-1", "user-1"))

    stored = sessions.batches[0]
    start, end = stored[1:3]
    assert start["event_type"] == "tool_call_start"
    assert end["event_type"] == "tool_call_end"
    assert start["tool_call_id"] == end["tool_call_id"] == "search-1"
    assert start["source"] == end["source"] == "procurement_analyst"
    assert start["payload"]["args"] == {"keyword": "FR7DC+"}


def test_session_events_become_the_existing_timeline_shape() -> None:
    from api_view.chat_service import _serialize_session_timeline

    timeline = _serialize_session_timeline(
        [
            {
                "event_id": "user-1",
                "event_type": "user_message",
                "source": "user",
                "payload": {"content": "find FR7DC+"},
            },
            {
                "event_id": "route-1",
                "event_type": "agent_routing",
                "source": "motorparts-agent",
                "payload": {
                    "tool_call_id": "task-1",
                    "subagent_type": "procurement_analyst",
                    "description": "Find the part.",
                },
            },
            {
                "event_id": "start-1",
                "event_type": "tool_call_start",
                "source": "procurement_analyst",
                "payload": {
                    "tool_call_id": "search-1",
                    "tool_name": "part_search",
                    "args": {"keyword": "FR7DC+"},
                },
            },
            {
                "event_id": "end-1",
                "event_type": "tool_call_end",
                "source": "procurement_analyst",
                "payload": {
                    "tool_call_id": "search-1",
                    "tool_name": "part_search",
                    "result": '{"items": []}',
                    "tool_status": "success",
                },
            },
        ]
    )

    assert [item["kind"] for item in timeline] == [
        "user",
        "agent_routing",
        "tool_call",
        "tool_result",
    ]
    assert timeline[2]["status"] == "success"
    assert timeline[2]["tool_args"] == {"keyword": "FR7DC+"}
    assert timeline[3]["tool_call_id"] == "search-1"


class SessionHistoryRepository:
    def __init__(self, events: list[dict[str, object]], *, owned: bool = True) -> None:
        self._events = events
        self._owned = owned

    async def get_session_events(self, *_: object) -> list[dict[str, object]]:
        return self._events

    async def owns_session(self, *_: object) -> bool:
        return self._owned


class HistoryGraph:
    async def aget_state(self, _: object) -> object:
        raise AssertionError("event history should be preferred over checkpoint fallback")


@pytest.mark.anyio
async def test_session_history_prefers_event_log_and_enforces_checkpoint_ownership() -> None:
    from api_view.chat_service import ChatService

    events = [
        {
            "event_id": "assistant-1",
            "event_type": "assistant_text",
            "source": "procurement_analyst",
            "namespace": ["tools:procurement_analyst"],
            "payload": {"content": "Part found."},
        }
    ]
    service = ChatService(HistoryGraph(), SessionHistoryRepository(events))

    history = await service.get_session_messages("thread-1", "user-1")

    assert history["messages"][0]["actor_name"] == "procurement_analyst"
    assert history["messages"][0]["namespace"] == ["tools:procurement_analyst"]

    denied = ChatService(HistoryGraph(), SessionHistoryRepository([], owned=False))
    assert await denied.get_session_messages("thread-1", "other-user") == {"messages": []}


def test_checkpoint_messages_become_a_flat_timeline_with_tool_results() -> None:
    from api_view.chat_service import _serialize_timeline

    timeline = _serialize_timeline(
        [
            HumanMessage(content="show order status", id="human-1"),
            AIMessage(
                content="",
                id="ai-1",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "order_search_details",
                        "args": {"partName": "brake pad"},
                    }
                ],
            ),
            ToolMessage(
                content='{"orders": 3}',
                id="tool-1",
                tool_call_id="call-1",
                name="order_search_details",
            ),
            AIMessage(content="Three orders were found.", id="ai-2"),
        ]
    )

    assert [item["kind"] for item in timeline] == ["user", "tool_call", "tool_result", "assistant"]
    assert timeline[1]["tool_name"] == "order_search_details"
    assert timeline[1]["tool_args"] == {"partName": "brake pad"}
    assert timeline[1]["status"] == "success"
    assert timeline[2]["tool_call_id"] == "call-1"
    assert timeline[2]["content"] == '{"orders": 3}'


def test_semantic_events_distinguish_routing_from_tool_calls() -> None:
    from api_view.chat_service import (
        _semantic_calls_from_state,
        _semantic_message_events,
    )

    task = AIMessage(
        content="",
        id="ai-routing",
        name="motorparts-agent",
        tool_calls=[
            {
                "id": "call-task",
                "name": "task",
                "args": {
                    "subagent_type": "procurement_analyst",
                    "description": "Find the requested part.",
                },
            }
        ],
    )
    tool = AIMessage(
        content="",
        id="ai-tool",
        name="procurement_analyst",
        tool_calls=[
            {
                "id": "call-search",
                "name": "part_search",
                "args": {"keyword": "FR7DC+"},
            }
        ],
    )
    events = _semantic_calls_from_state(
        {"messages": [task, tool]}, "thread-1", ["tools:subagent"], set()
    )

    assert [event["event"] for event in events] == [
        "agent_routing",
        "tool_call_start",
    ]
    assert events[0]["data"] == {
        "tool_call_id": "call-task",
        "tool_call_index": 0,
        "subagent_type": "procurement_analyst",
        "description": "Find the requested part.",
    }
    assert events[1]["data"]["args"] == {"keyword": "FR7DC+"}

    task_result = ToolMessage("internal summary", name="task", tool_call_id="call-task")
    tool_result = ToolMessage('{"items": []}', name="part_search", tool_call_id="call-search")
    assert _semantic_message_events(task_result, "thread-1", [], {}) == []
    end_events = _semantic_message_events(tool_result, "thread-1", [], {})
    assert end_events[0]["event"] == "tool_call_end"


def test_plain_execute_result_only_emits_tool_end() -> None:
    from api_view.chat_service import _semantic_message_events

    events = _semantic_message_events(
        ToolMessage(content="average=12.3", name="execute", tool_call_id="call-execute"),
        "thread-1", [], {},
    )

    assert [event["event"] for event in events] == ["tool_call_end"]


def test_execute_chart_document_remains_a_regular_tool_result() -> None:
    from api_view.chat_service import _semantic_message_events

    stdout = (
        "calculation complete\n"
        '{"type":"chart","version":"1.0","charts":[{'
        '"id":"price","chart_type":"bar","title":"Price",'
        '"x":"supplier","y":"value","data":[{"supplier":"A","value":1}],'
        '"provenance":["order_search_details"],"warnings":[]}]}'
    )
    events = _semantic_message_events(
        ToolMessage(content=stdout, name="execute", tool_call_id="call-execute", id="tool-execute"),
        "thread-1", [], {},
    )

    assert [event["event"] for event in events] == ["tool_call_end"]
    assert events[0]["data"]["result"] == stdout


def test_invalid_execute_chart_document_remains_a_regular_tool_result() -> None:
    from api_view.chat_service import _semantic_message_events

    stdout = '{"type":"chart","version":"1.0","charts":[{"id":"missing-fields"}]}'
    events = _semantic_message_events(
        ToolMessage(content=stdout, name="execute", tool_call_id="call-execute"),
        "thread-1", [], {},
    )

    assert [event["event"] for event in events] == ["tool_call_end"]
