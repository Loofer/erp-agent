import httpx

from agent.tools import build_parent_tools, build_subagent_only_tools
from agent.tools.customers_tools import build_customer_tools
from agent.tools.http_base import ApiClient
from agent.tools.inventory_tools import build_inventory_tools
from agent.tools.logistics_tools import build_logistics_tools
from agent.tools.orders_tools import build_order_tools
from agent.tools.parts_tools import build_part_tools
from agent.tools.suppliers_tools import build_supplier_tools


def test_parent_tools_are_limited_to_read_only_domain_operations(
    client: object
) -> None:
    tools = build_parent_tools(client)

    assert [tool.name for tool in tools] == ["get_dashboard"]


def test_subagent_only_tools_are_not_registered_on_the_parent(
    client: object
) -> None:
    tools = build_subagent_only_tools(client)

    assert [tool.name for tool in tools] == [
        "create_supplier",
        "search_suppliers",
        "request_order_info",
    ]


def test_future_domain_modules_expose_no_tools_yet() -> None:
    assert build_part_tools() == []
    assert build_order_tools() == []
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
