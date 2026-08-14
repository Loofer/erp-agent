"""Validated declarative configuration for subagents."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from deepagents import FilesystemMiddleware, SubAgent
from deepagents.backends import LocalShellBackend

from agent.middlewares.pii_middleware import tool_call_limit_middleware

SubagentBackend = Literal["local_shell"]


@dataclass(frozen=True)
class SubagentDefinition:
    """An inert subagent description loaded from application configuration."""

    name: str
    description: str
    system_prompt: str
    model: str | None
    tools: tuple[str, ...]
    interrupt_on: dict[str, bool | dict[str, list[str]]] = field(default_factory=dict)
    skills: tuple[str, ...] = ()
    backend: SubagentBackend | None = None


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
    backend = _backend(document, path)
    interrupt_on = _interrupt_on(document, path)
    skills = _skills(document, path)
    return SubagentDefinition(
        name=name,
        description=description,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        interrupt_on=interrupt_on,
        skills=skills,
        backend=backend,
    )


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


def _backend(document: Mapping[object, object], path: Path) -> SubagentBackend | None:
    value = _optional_string(document, "backend", path)
    if value is None:
        return None
    if value != "local_shell":
        raise SubagentConfigurationError(
            f"{path.name} field 'backend' must be 'local_shell'."
        )
    return "local_shell"


def _interrupt_on(
    document: Mapping[object, object], path: Path
) -> dict[str, bool | dict[str, list[str]]]:
    if "interrupt_on" not in document:
        return {}

    value = document["interrupt_on"]
    if not isinstance(value, Mapping):
        raise SubagentConfigurationError(
            f"{path.name} field 'interrupt_on' must be a mapping."
        )

    parsed: dict[str, bool | dict[str, list[str]]] = {}
    for tool_name, config in value.items():
        name = _non_empty_string(tool_name, "interrupt_on tool name", path)
        if isinstance(config, bool):
            parsed[name] = config
            continue
        if not isinstance(config, Mapping):
            raise SubagentConfigurationError(
                f"{path.name} interrupt_on '{name}' must be a boolean or mapping."
            )
        decisions = config.get("allowed_decisions")
        if not isinstance(decisions, list) or not decisions:
            raise SubagentConfigurationError(
                f"{path.name} interrupt_on '{name}' needs allowed_decisions."
            )
        parsed[name] = {
            "allowed_decisions": [
                _non_empty_string(decision, f"interrupt_on {name} decision", path)
                for decision in decisions
            ]
        }
    return parsed


def _skills(document: Mapping[object, object], path: Path) -> tuple[str, ...]:
    if "skills" not in document:
        return ()

    value = document["skills"]
    if not isinstance(value, list):
        raise SubagentConfigurationError(f"{path.name} field 'skills' must be a list.")
    return tuple(
        _non_empty_string(skill, f"skills[{index}]", path)
        for index, skill in enumerate(value)
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
    *,
    backend_root: Path | None = None,
) -> list[SubAgent]:
    """Convert validated YAML definitions to Deep Agents SubAgent instances."""
    subagents: list[SubAgent] = []
    for definition in definitions:
        tools: list[object] = []
        for tool_name in definition.tools:
            try:
                tools.append(tools_by_name[tool_name])
            except KeyError as error:
                raise SubagentConfigurationError(
                    f"{definition.name} references unknown tool: {tool_name}"
                ) from error

        sub_agent = SubAgent(
            name=definition.name,
            description=definition.description,
            system_prompt=definition.system_prompt,
            tools=tools,
            interrupt_on=definition.interrupt_on or None,
            skills=list(definition.skills) if definition.skills else None,
        )
        # Only set `model` when explicitly configured.  SubAgent is a TypedDict
        # (plain dict), so spec.get("model", parent_model) in deepagents' graph
        # falls back to the parent model when the key is absent.  Passing
        # model=None keeps the key present with a None value, which causes
        # resolve_model(None) → init_chat_model(None) → _ConfigurableModel and
        # a subsequent TypeError in create_summarization_middleware.
        if definition.model is not None:
            sub_agent["model"] = definition.model
        if definition.backend == "local_shell":
            if backend_root is None:
                raise SubagentConfigurationError(
                    f"{definition.name} requires a backend_root for local_shell."
                )
            sub_agent["middleware"] = [
                FilesystemMiddleware(
                    backend=LocalShellBackend(
                        root_dir=backend_root,
                        inherit_env=True,
                    ),
                ),
                tool_call_limit_middleware
            ]
        subagents.append(sub_agent)
    return subagents
