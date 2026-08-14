"""HTTP boundary for ordinary in-process domain tools."""

import logging
from typing import Any

import httpx

_log = logging.getLogger(__name__)


class ApiClientError(RuntimeError):
    """Raised for transport, HTTP, or malformed API response failures."""


class ApiClient:
    """Send requests to the configured Motorparts API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else None
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
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
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Request for {operation} failed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raw_body = exc.response.text
            _log.error("Motorparts %s returned HTTP %s: %s", operation, exc.response.status_code, raw_body)
            raise ApiClientError(
                f"Request for {operation} failed with HTTP {exc.response.status_code}: "
                f"{raw_body}"
            ) from exc

        try:
            payload: Any = response.json()
        except ValueError as exc:
            _log.error("Motorparts %s returned a non-JSON body: %s", operation, response.text)
            raise ApiClientError(
                f"Response for {operation} was not JSON: {response.text}"
            ) from exc
        if not isinstance(payload, dict):
            _log.error("Motorparts %s returned a non-object body: %s", operation, response.text)
            raise ApiClientError(f"Response for {operation} was not an object.")
        code = payload.get("code")
        if isinstance(code, int) and code >= 400:
            _log.error("Motorparts %s returned error code %s: %s", operation, code, response.text)
            raise ApiClientError(
                f"API operation {operation} failed with code {code}: {response.text}"
            )
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
