import json

import httpx

from agent.tools import build_subagent_only_tools
from agent.tools.customers_tools import build_customer_tools
from agent.tools.hitl_tools import request_supplier_info
from agent.tools.http_base import ApiClient
from agent.tools.inventory_tools import build_inventory_tools
from agent.tools.logistics_tools import build_logistics_tools
from agent.tools.orders_tools import build_order_tools
from agent.tools.parts_tools import build_part_tools
from agent.tools.suppliers_tools import build_supplier_tools


def test_subagent_only_tools_are_not_registered_on_the_parent(
    client: object
) -> None:
    tools = build_subagent_only_tools(client)

    assert [tool.name for tool in tools] == [
        "create_supplier",
        "search_suppliers",
        "create_order",
        "update_order",
        "request_order_info",
        "request_supplier_info",
    ]


def test_future_domain_modules_expose_no_tools_yet() -> None:
    assert build_part_tools() == []
    assert build_inventory_tools() == []
    assert build_logistics_tools() == []
    assert build_customer_tools() == []


def test_supplier_tool_exposes_a_parseable_payload_contract(
    client: object
) -> None:
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
    assert [(request.method, request.url.path, request.url.query) for request in requests] == [
        ("GET", "/api/suppliers/search", b"name=Acme"),
    ]


def test_create_order_posts_complete_order_payload() -> None:
    requests: list[httpx.Request] = []
    order = {
        "orderNumber": "PO-20260804-001",
        "totalAmount": 120.0,
        "status": 0,
        "orderTime": "2026-08-04T07:11:58.664Z",
        "expectedDeliveryDate": "2026-08-11",
        "actualDeliveryDate": "2026-08-11",
        "createdBy": 1,
        "remark": "Urgent replenishment",
        "orderDetail": [
            {
                "partId": 1001,
                "quantity": 2,
                "unitPrice": 60.0,
                "subtotal": 120.0,
                "remark": "",
                "partDetail": {"partCode": "P-001", "name": "Brake pad"},
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

    assert order_tool.invoke({"order": order}) == {"code": 0, "data": order}
    assert [(request.method, request.url.path, json.loads(request.content)) for request in requests] == [
        ("POST", "/api/orders/create", order),
    ]


def test_update_order_puts_complete_order_payload() -> None:
    requests: list[httpx.Request] = []
    order = {
        "id": 42,
        "orderNumber": "PO-20260804-001",
        "totalAmount": 120.0,
        "status": 0,
        "orderDetail": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": order})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    order_tool = build_order_tools(client)[1]

    assert order_tool.invoke({"order_id": 42, "order": order}) == {
        "code": 0,
        "data": order,
    }
    assert [(request.method, request.url.path, json.loads(request.content)) for request in requests] == [
        ("PUT", "/api/orders/update/42", order),
    ]


def test_request_supplier_info_returns_the_current_draft() -> None:
    draft = {"supplierCode": "SUP-001", "name": "Acme"}

    assert request_supplier_info.invoke(
        {"supplier_draft": draft, "missing_fields": ["phone", "address"]}
    ) == {
        "status": "human_input_requested",
        "supplier_draft": draft,
        "missing_fields": ["phone", "address"],
    }
