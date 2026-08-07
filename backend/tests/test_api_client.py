import httpx
import pytest

from agent.tools.http_base import ApiClient, ApiClientError


def test_request_sends_a_get_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"orders": 4}})

    client = ApiClient("https://motorparts.test", transport=httpx.MockTransport(handler))
    assert client.get("/api/statistics/dashboard") == {
        "code": 200,
        "data": {"orders": 4},
    }
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/statistics/dashboard")
    ]


def test_request_sends_a_post_request_with_json_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {}})

    client = ApiClient("https://motorparts.test", transport=httpx.MockTransport(handler))
    assert client.post(
        "/api/suppliers/create",
        {"supplierCode": "S-001", "name": "Acme Parts"},
    ) == {"code": 200, "data": {}}
    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", "/api/suppliers/create")
    ]


def test_request_rejects_non_object_responses() -> None:
    client = ApiClient(
        "https://motorparts.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=["unexpected"])
        ),
    )

    with pytest.raises(ApiClientError, match="was not an object"):
        client.get("/api/statistics/dashboard")


def test_request_logs_raw_erp_error_response(caplog: pytest.LogCaptureFixture) -> None:
    client = ApiClient(
        "https://motorparts.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, text='{"message":"invalid part"}')
        ),
    )

    with pytest.raises(ApiClientError, match="invalid part"):
        client.post("/api/orders/create", {"orderNumber": "PO-001"})

    assert 'ERP POST /api/orders/create returned HTTP 400: {"message":"invalid part"}' in caplog.text
