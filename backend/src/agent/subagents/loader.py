"""Validated declarative configuration for subagents."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SubagentDefinition:
    """An inert subagent description loaded from application configuration."""

    name: str
    description: str
    system_prompt: str
    model: str | None
    tools: tuple[str, ...]


class SubagentConfigurationError(ValueError):
    """Raised when a declarative subagent definition is invalid."""


def load_subagent_definitions(directory: Path) -> tuple[SubagentDefinition, ...]:
    """Load every YAML definition in a directory and validate unique names."""
    if not directory.is_dir():
        raise SubagentConfigurationError(
            f"Subagent configuration directory does not exist: {directory}"
        )

    definitions = tuple(_load_definition(path) for path in sorted(directory.glob("*.yaml")))
    _validate_unique_names(definitions)
    return definitions


def _load_definition(path: Path) -> SubagentDefinition:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SubagentConfigurationError(f"Unable to read {path.name}: {error}") from error
    except yaml.YAMLError as error:
        raise SubagentConfigurationError(f"Invalid YAML in {path.name}: {error}") from error

    if not isinstance(document, Mapping):
        raise SubagentConfigurationError(f"{path.name} must contain a mapping.")

    name = _required_string(document, "name", path)
    description = _required_string(document, "description", path)
    system_prompt = _required_string(document, "system_prompt", path)
    model = _optional_string(document, "model", path)
    tools = _tools(document, path)
    return SubagentDefinition(name, description, system_prompt, model, tools)


def _required_string(document: Mapping[object, object], field: str, path: Path) -> str:
    if field not in document:
        raise SubagentConfigurationError(f"{path.name} is missing required field '{field}'.")
    return _non_empty_string(document[field], field, path)


def _optional_string(
    document: Mapping[object, object], field: str, path: Path
) -> str | None:
    if field not in document:
        return None
    return _non_empty_string(document[field], field, path)


def _tools(document: Mapping[object, object], path: Path) -> tuple[str, ...]:
    if "tools" not in document:
        return ()

    value = document["tools"]
    if not isinstance(value, list):
        raise SubagentConfigurationError(f"{path.name} field 'tools' must be a list.")
    return tuple(
        _non_empty_string(tool, f"tools[{index}]", path)
        for index, tool in enumerate(value)
    )


def _non_empty_string(value: object, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SubagentConfigurationError(
            f"{path.name} field '{field}' must be a non-empty string."
        )
    return value


def _validate_unique_names(definitions: tuple[SubagentDefinition, ...]) -> None:
    names: set[str] = set()
    for definition in definitions:
        if definition.name in names:
            raise SubagentConfigurationError(
                f"Duplicate subagent definition name: {definition.name}"
            )
        names.add(definition.name)


def to_deep_agent_subagents(
    definitions: tuple[SubagentDefinition, ...],
    tools_by_name: Mapping[str, object],
) -> list[dict[str, Any]]:
    """Convert validated YAML definitions to Deep Agents subagent dictionaries."""
    subagents: list[dict[str, Any]] = []
    for definition in definitions:
        tools: list[object] = []
        for tool_name in definition.tools:
            try:
                tools.append(tools_by_name[tool_name])
            except KeyError as error:
                raise SubagentConfigurationError(
                    f"{definition.name} references unknown tool: {tool_name}"
                ) from error
        subagent: dict[str, Any] = {
            "name": definition.name,
            "description": definition.description,
            "system_prompt": definition.system_prompt,
            "tools": tools,
        }
        if definition.model is not None:
            subagent["model"] = definition.model
        subagents.append(subagent)
    return subagents
