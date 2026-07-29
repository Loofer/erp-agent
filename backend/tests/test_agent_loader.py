from pathlib import Path

import pytest

from agent.subagents.loader import (
    SubagentConfigurationError,
    SubagentDefinition,
    load_subagent_definitions,
)
from api_view.agent_loader import AgentLoader


def write_definition(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content, encoding="utf-8")


def test_load_subagent_definitions_reads_valid_yaml(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        "researcher.yaml",
        """name: researcher
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
tools:
  - web_search
""",
    )

    definitions = load_subagent_definitions(tmp_path)

    assert definitions == (
        SubagentDefinition(
            name="researcher",
            description="Investigates supplier and market questions.",
            system_prompt="Gather evidence before responding.",
            model=None,
            tools=("web_search",),
        ),
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("- not-a-mapping", "malformed.yaml"),
        (
            """name: researcher
description: Investigates supplier and market questions.
""",
            "system_prompt",
        ),
        (
            """name: researcher
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
tools: web_search
""",
            "tools",
        ),
    ],
)
def test_load_subagent_definitions_rejects_invalid_yaml(
    tmp_path: Path, content: str, message: str
) -> None:
    write_definition(tmp_path, "malformed.yaml", content)

    with pytest.raises(SubagentConfigurationError, match=message):
        load_subagent_definitions(tmp_path)


def test_load_subagent_definitions_rejects_duplicate_names(tmp_path: Path) -> None:
    valid_definition = """name: researcher
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
"""
    write_definition(tmp_path, "first.yaml", valid_definition)
    write_definition(tmp_path, "second.yaml", valid_definition)

    with pytest.raises(SubagentConfigurationError, match="researcher"):
        load_subagent_definitions(tmp_path)


def test_agent_loader_caches_validated_subagents(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        "researcher.yaml",
        """name: researcher
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
""",
    )
    calls = 0

    def graph_factory(definitions: tuple[SubagentDefinition, ...]) -> object:
        nonlocal calls
        calls += 1
        return definitions

    loader = AgentLoader(tmp_path, graph_factory)

    first = loader.load_subagents()
    (tmp_path / "researcher.yaml").unlink()
    second = loader.load_subagents()

    assert first is second
    assert calls == 0


def test_agent_loader_loads_definitions_before_building_graph(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        "researcher.yaml",
        """name: researcher
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
""",
    )
    events: list[str] = []

    def graph_factory(definitions: tuple[SubagentDefinition, ...]) -> object:
        events.append(definitions[0].name)
        return object()

    loader = AgentLoader(tmp_path, graph_factory)
    graph = loader.load_agent_graph()

    assert graph is not None
    assert events == ["researcher"]


def test_agent_loader_rejects_invalid_definitions_before_building_graph(
    tmp_path: Path,
) -> None:
    write_definition(tmp_path, "invalid.yaml", "name: researcher")
    factory_calls = 0

    def graph_factory(definitions: tuple[SubagentDefinition, ...]) -> object:
        nonlocal factory_calls
        factory_calls += 1
        return definitions

    loader = AgentLoader(tmp_path, graph_factory)

    with pytest.raises(SubagentConfigurationError, match="invalid.yaml"):
        loader.load_agent_graph()

    assert factory_calls == 0
