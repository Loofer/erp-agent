"""Fixed read-only Motorparts responses for offline agent evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

_SUPPLIER = {
    "id": 1, "supplierCode": "SUP-001", "name": "Northwind Components",
    "contactPerson": "Lin", "creditRating": "A", "status": 1,
}
_PART = {
    "id": 1001, "partCode": "BP-100", "name": "Brake Pad",
    "model": "MP-2024", "specification": "Standard", "unit": "set",
    "purchasePrice": 60, "stockWarningValue": 20, "supplierId": 1,
}
_ORDER_DETAIL = {
    "id": 11, "orderId": 101, "partId": 1001, "quantity": 20,
    "unitPrice": 60, "subtotal": 1200, "partDetail": {**_PART, "supplier": _SUPPLIER},
}
_WARNING = {
    "id": 21, "partId": 1001, "currentQuantity": 8, "safetyStock": 20,
    "warehouseLocation": "A-01", "partDetail": _PART,
}


@dataclass
class MotorpartsFixture:
    """MockTransport-backed Motorparts API with request recording."""

    requests: list[dict[str, object]] = field(default_factory=list)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def client(self) -> object:
        from agent.tools.http_base import ApiClient

        return ApiClient("https://motorparts.fixture", transport=self.transport())

    def _handle(self, request: httpx.Request) -> httpx.Response:
        query = dict(request.url.params)
        body = json.loads(request.content) if request.content else None
        self.requests.append({"method": request.method, "path": request.url.path, "query": query, "body": body})
        if request.method != "GET":
            return httpx.Response(405, json={"code": 405, "message": "fixture is read-only"})
        payload: object
        if request.url.path == "/api/suppliers/search":
            payload = [_SUPPLIER]
        elif request.url.path in {"/api/parts/search", "/api/parts/supplier/1"}:
            payload = [_PART]
        elif request.url.path == "/api/orders/search-details":
            payload = [_ORDER_DETAIL]
        elif request.url.path == "/api/inventory/warning":
            payload = [_WARNING]
        else:
            return httpx.Response(404, json={"code": 404, "message": "unknown fixture path"})
        return httpx.Response(200, json={"code": 0, "message": "ok", "data": payload})
