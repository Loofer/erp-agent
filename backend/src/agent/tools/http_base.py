"""HTTP boundary for ordinary in-process domain tools."""

from typing import Any

import httpx


class ApiClientError(RuntimeError):
    """Raised for transport, HTTP, or malformed API response failures."""


class ApiClient:
    """Send requests to the configured ERP API."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, object] | None = None,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Perform an HTTP request and return its JSON object response."""
        operation = f"{method.upper()} {path}"
        try:
            response = self._client.request(
                method.upper(),
                path,
                params=query or {},
                json=body,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Request for {operation} failed: {exc}") from exc
        except ValueError as exc:
            raise ApiClientError(f"Response for {operation} was not JSON.") from exc
        if not isinstance(payload, dict):
            raise ApiClientError(f"Response for {operation} was not an object.")
        code = payload.get("code")
        if isinstance(code, int) and code >= 400:
            raise ApiClientError(f"API operation {operation} failed with code {code}.")
        return payload

    def get(
        self, path: str, *, query: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Send a GET request."""
        return self.request("GET", path, query=query, body=None)

    def post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        """Send a JSON POST request."""
        return self.request("POST", path, body=body)

    def put(self, path: str, body: dict[str, object]) -> dict[str, object]:
        """Send a JSON PUT request."""
        return self.request("PUT", path, body=body)
