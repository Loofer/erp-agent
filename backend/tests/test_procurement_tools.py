import httpx

from agent.tools import build_subagent_only_tools
from agent.tools.http_base import ApiClient


def test_procurement_analysis_tools_use_documented_read_endpoints() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 0, "data": []})

    client = ApiClient(
        "https://motorparts.test", transport=httpx.MockTransport(handler)
    )
    tools = {tool.name: tool for tool in build_subagent_only_tools(client)}

    assert tools["supplier_query"].invoke({"name": "Acme"}) == {
        "code": 0,
        "data": [],
    }
    assert tools["part_query"].invoke({"name": "Bearing"}) == {
        "code": 0,
        "data": [],
    }
    assert tools["part_search"].invoke({"name": "Bolt"}) == {"code": 0, "data": []}
    assert tools["part_by_supplier"].invoke({"supplier_id": 42}) == {
        "code": 0,
        "data": [],
    }
    assert tools["order_search_details"].invoke(
        {"partName": "Bearing", "startDate": "2026-08-01", "endDate": "2026-08-07"}
    ) == {"code": 0, "data": []}
    assert tools["inventory_warning"].invoke({}) == {"code": 0, "data": []}

    assert [(request.method, request.url.path, request.url.query) for request in requests] == [
        ("GET", "/api/suppliers/search", b"name=Acme"),
        ("GET", "/api/parts/search", b"name=Bearing"),
        ("GET", "/api/parts/search", b"name=Bolt"),
        ("GET", "/api/parts/supplier/42", b""),
        (
            "GET",
            "/api/orders/search-details",
            b"partName=Bearing&startDate=2026-08-01&endDate=2026-08-07",
        ),
        ("GET", "/api/inventory/warning", b""),
    ]
