import json
from typing import TypedDict

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.tools import build_subagent_only_tools
from agent.tools.customers_tools import build_customer_tools
from agent.tools.hitl_tools import request_order_info, request_supplier_info
from agent.tools.http_base import ApiClient
from agent.tools.logistics_tools import build_logistics_tools
from agent.tools.orders_tools import build_order_tools
from agent.tools.suppliers_tools import build_supplier_tools


def test_subagent_only_tools_are_not_registered_on_the_parent(client: object) -> None:
    tools = build_subagent_only_tools(client)

    assert [tool.name for tool in tools] == [
        "create_supplier",
        "search_suppliers",
        "supplier_query",
        "part_query",
        "part_search",
        "part_by_supplier",
        "inventory_warning",
        "create_order",
        "update_order",
        "order_search_details",
        "request_order_info",
        "request_supplier_info",
    ]


def test_unimplemented_domain_modules_expose_no_tools_yet() -> None:
    assert build_logistics_tools() == []
    assert build_customer_tools() == []


def test_supplier_tool_exposes_a_parseable_payload_contract(client: object) -> None:
    supplier_tool = build_supplier_tools(client)[0]

    schema = supplier_tool.args_schema.model_json_schema()

    assert set(schema["required"]) >= {
        "supplierCode",
        "name",
        "contactPerson",
        "phone",
        "email",
        "address",
        "creditRating",
    }


def test_search_suppliers_uses_name_query_parameter() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": []})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    supplier_tool = build_supplier_tools(client)[1]

    assert supplier_tool.invoke({"name": "Acme"}) == {"code": 0, "data": []}
    assert [
        (request.method, request.url.path, request.url.query) for request in requests
    ] == [("GET", "/api/suppliers/search", b"name=Acme")]


def test_create_order_posts_normalized_payload() -> None:
    requests: list[httpx.Request] = []
    order = {
        "deleted": 0,
        "orderNumber": "PO-20260804-001",
        "totalAmount": None,
        "status": 0,
        "orderTime": "2026-08-04T07:11:58.664Z",
        "expectedDeliveryDate": "2026-08-11",
        "actualDeliveryDate": None,
        "createdBy": 1,
        "remark": "Urgent replenishment",
        "orderDetail": [
            {
                "deleted": 0,
                "partId": 1001,
                "quantity": 2,
                "unitPrice": 60.0,
                "subtotal": 120.0,
                "remark": "",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": order})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    order_tool = build_order_tools(client)[0]

    assert order_tool.invoke({"order_payload": order}) == {"code": 0, "data": order}
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/orders/create"),
    ]
    request_payload = json.loads(requests[0].content)
    assert request_payload["orderDetail"][0]["quantity"] == 2
    assert request_payload["orderTime"] == "2026-08-04T07:11:58.664Z"
    assert "totalAmount" not in request_payload
    assert "actualDeliveryDate" not in request_payload


def test_update_order_puts_normalized_payload() -> None:
    requests: list[httpx.Request] = []
    order = {
        "deleted": 0,
        "orderNumber": "PO-20260804-001",
        "totalAmount": 120.0,
        "status": 0,
        "orderTime": "2026-08-04T07:11:58.664Z",
        "expectedDeliveryDate": "2026-08-11",
        "actualDeliveryDate": None,
        "createdBy": 1,
        "remark": "Urgent replenishment",
        "orderDetail": [
            {
                "deleted": 0,
                "partId": 1001,
                "quantity": 2,
                "unitPrice": 60.0,
                "subtotal": 120.0,
                "remark": "",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": order})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    order_tool = build_order_tools(client)[1]

    assert order_tool.invoke({"order_id": 42, "order_payload": order}) == {
        "code": 0,
        "data": order,
    }
    assert [(request.method, request.url.path) for request in requests] == [
        ("PUT", "/api/orders/update/42"),
    ]
    assert "actualDeliveryDate" not in json.loads(requests[0].content)


def test_order_payload_converts_whole_number_quantity_to_integer() -> None:
    order = {
        "orderNumber": "PO-001",
        "orderDetail": [{"partId": 1001, "quantity": 800.0, "unitPrice": 60}],
    }
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    order_tool = build_order_tools(client)[0]

    assert order_tool.invoke({"order_payload": order}) == {"code": 0, "data": {}}
    assert json.loads(requests[0].content)["orderDetail"][0]["quantity"] == 800


def test_request_order_info_returns_complete_without_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "agent.tools.hitl_tools.interrupt",
        lambda value: pytest.fail("complete draft must not interrupt"),
    )

    assert request_order_info.invoke(
        {"order_draft": {"orderNumber": "PO-001"}, "missing_fields": []}
    ) == {
        "status": "complete",
        "order_draft": {"orderNumber": "PO-001"},
        "missing_fields": [],
    }


def test_request_order_info_forwards_agent_supplied_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interrupts: list[dict[str, object]] = []

    def fake_interrupt(value: dict[str, object]) -> str:
        interrupts.append(value)
        return "createdBy is 7"

    monkeypatch.setattr("agent.tools.hitl_tools.interrupt", fake_interrupt)

    result = request_order_info.invoke(
        {
            "order_draft": {"orderNumber": "PO-001"},
            "missing_fields": ["createdBy", "orderDetail[0].quantity"],
            "message": "Please provide the creator and first-line quantity.",
        }
    )

    assert result == {
        "status": "human_input_received",
        "order_draft": {"orderNumber": "PO-001"},
        "missing_fields": ["createdBy", "orderDetail[0].quantity"],
        "human_response": "createdBy is 7",
    }
    assert interrupts == [
        {
            "kind": "tool_input",
            "tool_name": "request_order_info",
            "message": "Please provide the creator and first-line quantity.",
            "order_draft": {"orderNumber": "PO-001"},
            "missing_fields": ["createdBy", "orderDetail[0].quantity"],
        }
    ]


def test_request_order_info_pauses_and_resumes_with_langgraph() -> None:
    class State(TypedDict, total=False):
        order_draft: dict[str, object]
        result: dict[str, object]

    def collect_order_info(state: State) -> State:
        result = request_order_info.invoke(
            {
                "order_draft": state["order_draft"],
                "missing_fields": ["createdBy"],
                "message": "Please provide the creator.",
            }
        )
        return {"result": result}

    builder = StateGraph(State)
    builder.add_node("collect_order_info", collect_order_info)
    builder.add_edge(START, "collect_order_info")
    builder.add_edge("collect_order_info", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "order-info-test"}}

    paused = graph.invoke({"order_draft": {"orderNumber": "PO-001"}}, config)
    resumed = graph.invoke(Command(resume="createdBy is 7"), config)

    assert paused["__interrupt__"][0].value["kind"] == "tool_input"
    assert paused["__interrupt__"][0].value["missing_fields"] == ["createdBy"]
    assert resumed["result"]["human_response"] == "createdBy is 7"


def test_request_supplier_info_returns_the_current_draft() -> None:
    draft = {"supplierCode": "SUP-001", "name": "Acme"}

    assert request_supplier_info.invoke(
        {"supplier_draft": draft, "missing_fields": ["phone", "address"]}
    ) == {
        "status": "human_input_requested",
        "supplier_draft": draft,
        "missing_fields": ["phone", "address"],
    }
