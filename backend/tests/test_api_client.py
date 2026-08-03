import httpx
import pytest

from agent.tools.http_base import ApiClient, ApiClientError
from agent.tools.openapi import Operation


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


def test_execute_rejects_direct_mutation_without_sending_a_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {}})

    client = ApiClient("https://motorparts.test", transport=httpx.MockTransport(handler))
    operation = Operation("create", "POST", "/api/suppliers/create")

    with pytest.raises(ApiClientError, match="must be staged and approved"):
        client.execute(
            operation,
            path_params={},
            query={},
            body={"supplierCode": "S-001", "name": "Acme Parts"},
        )

    assert requests == []
