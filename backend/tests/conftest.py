import sys
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from agent.tools.http_base import ApiClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


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
