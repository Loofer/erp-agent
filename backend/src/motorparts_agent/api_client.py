"""Small synchronous HTTP client for cataloged API operations."""

from typing import Any

import httpx

from .openapi import Operation


class ApiClientError(RuntimeError):
    """Raised for transport, HTTP, or malformed API response failures."""


class ApiClient:
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

    def execute(
        self,
        operation: Operation,
        *,
        path_params: dict[str, object],
        query: dict[str, object],
        body: dict[str, object] | None,
    ) -> dict[str, object]:
        """Send one already-authorized cataloged operation."""
        path = _render_path(operation, path_params)
        _validate_required(operation.required_query_params, query, "query")
        if operation.requires_body and body is None:
            raise ApiClientError(f"Operation {operation.name} requires a JSON body.")
        try:
            response = self._client.request(
                operation.method,
                path,
                params=query,
                json=body,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except httpx.HTTPError as exc:
            raise ApiClientError(f"Request for {operation.name} failed: {exc}") from exc
        except ValueError as exc:
            raise ApiClientError(f"Response for {operation.name} was not JSON.") from exc
        if not isinstance(payload, dict):
            raise ApiClientError(f"Response for {operation.name} was not an object.")
        code = payload.get("code")
        if isinstance(code, int) and code >= 400:
            raise ApiClientError(f"API operation {operation.name} failed with code {code}.")
        return payload


def _render_path(operation: Operation, path_params: dict[str, object]) -> str:
    _validate_required(operation.required_path_params, path_params, "path")
    path = operation.path
    for name, value in path_params.items():
        marker = "{" + name + "}"
        if marker not in path:
            raise ApiClientError(f"Unexpected path parameter for {operation.name}: {name}")
        path = path.replace(marker, str(value))
    if "{" in path or "}" in path:
        raise ApiClientError(f"Missing path parameters for {operation.name}.")
    return path


def _validate_required(
    required_names: tuple[str, ...], values: dict[str, object], location: str
) -> None:
    missing = [name for name in required_names if name not in values]
    if missing:
        joined = ", ".join(missing)
        raise ApiClientError(f"Missing required {location} parameters: {joined}")
