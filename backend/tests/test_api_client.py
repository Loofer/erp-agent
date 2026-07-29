import httpx

from motorparts_agent.api_client import ApiClient
from motorparts_agent.openapi import Operation


def test_execute_dashboard_uses_the_cataloged_get_operation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"orders": 4}})

    client = ApiClient("https://motorparts.test", transport=httpx.MockTransport(handler))
    operation = Operation("getDashboard", "GET", "/api/statistics/dashboard")

    assert client.execute(operation, path_params={}, query={}, body=None) == {
        "code": 200,
        "data": {"orders": 4},
    }
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/statistics/dashboard")
    ]
