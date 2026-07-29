"""OpenAPI operation metadata used to constrain agent actions."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OpenApiError(ValueError):
    """Raised when an OpenAPI contract cannot be safely loaded."""


@dataclass(frozen=True)
class Operation:
    name: str
    method: str
    path: str
    required_path_params: tuple[str, ...] = ()
    required_query_params: tuple[str, ...] = ()
    requires_body: bool = False

    @property
    def is_mutation(self) -> bool:
        return self.method.upper() != "GET"


def load_operation_catalog(path: Path) -> dict[str, Operation]:
    """Load immutable operation metadata keyed by OpenAPI operation ID."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OpenApiError(f"Unable to read OpenAPI contract: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OpenApiError(f"OpenAPI contract is not valid JSON: {path}") from exc

    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenApiError("OpenAPI contract does not contain a paths object.")

    catalog: dict[str, Operation] = {}
    for route, path_item in paths.items():
        if not isinstance(route, str) or not isinstance(path_item, dict):
            raise OpenApiError("OpenAPI paths must map route strings to path items.")
        for method, definition in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(definition, dict):
                raise OpenApiError(f"Operation definition for {method} {route} is invalid.")
            name = definition.get("operationId")
            if not isinstance(name, str) or not name:
                raise OpenApiError(f"Operation {method.upper()} {route} has no operationId.")
            if name in catalog:
                raise OpenApiError(f"OpenAPI operationId is not unique: {name}")
            parameters = definition.get("parameters", [])
            if not isinstance(parameters, list):
                raise OpenApiError(f"Parameters for operation {name} are invalid.")
            path_params = _required_parameter_names(parameters, "path")
            query_params = _required_parameter_names(parameters, "query")
            catalog[name] = Operation(
                name=name,
                method=method.upper(),
                path=route,
                required_path_params=path_params,
                required_query_params=query_params,
                requires_body="requestBody" in definition,
            )
    return catalog


def _required_parameter_names(parameters: list[Any], location: str) -> tuple[str, ...]:
    names: list[str] = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise OpenApiError("OpenAPI parameter is invalid.")
        if parameter.get("in") == location and parameter.get("required") is True:
            name = parameter.get("name")
            if not isinstance(name, str) or not name:
                raise OpenApiError("Required OpenAPI parameter has no name.")
            names.append(name)
    return tuple(names)
