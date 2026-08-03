from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from agent.tools.http_base import ApiClient
from agent.tools.openapi import Operation, load_operation_catalog


@pytest.fixture
def catalog() -> dict[str, Operation]:
    return load_operation_catalog(Path("openapi/swagger.json"))


@pytest.fixture
def requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def client(requests: list[httpx.Request]) -> ApiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"ok": True}})

    return ApiClient(
        "https://motorparts.test",
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture
def request_handler(requests: list[httpx.Request]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"code": 200, "data": {"ok": True}})

    return handler
