from pathlib import Path

import pytest
from deepagents import FilesystemMiddleware
from deepagents.backends import LocalShellBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

from agent.subagents.loader import (
    SubagentConfigurationError,
    SubagentDefinition,
    load_subagent_definitions,
    to_deep_agent_subagents,
)


def write_definition(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content, encoding="utf-8")


def test_load_subagent_definitions_reads_valid_yaml(tmp_path: Path) -> None:
    write_definition(
        tmp_path,
        "sample.yaml",
        """name: sample
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
""",
    )

    definitions = load_subagent_definitions(tmp_path)

    assert definitions == (
        SubagentDefinition(
            name="sample",
            description="Investigates supplier and market questions.",
            system_prompt="Gather evidence before responding.",
            model=None,
            tools=(),
        ),
    )


def test_shipped_subagent_definitions_cover_research_analysis_and_order() -> None:
    directory = Path(__file__).resolve().parents[1] / "src" / "agent" / "subagents" / "configs"

    definitions = load_subagent_definitions(directory)

    assert [(definition.name, definition.tools) for definition in definitions] == [
        (
            "procurement_analyst",
            (
                "supplier_query",
                "part_query",
                "part_search",
                "part_by_supplier",
                "order_search_details",
                "inventory_warning",
            ),
        ),
        ("procurement_order", ("request_order_info", "create_order", "update_order")),
        (
            "supplier_manager",
            ("request_supplier_info", "create_supplier", "search_suppliers"),
        ),
    ]
    order_definition = next(
        definition for definition in definitions if definition.name == "procurement_order"
    )
    analyst_definition = next(
        definition for definition in definitions if definition.name == "procurement_analyst"
    )
    assert analyst_definition.backend == "local_shell"
    assert analyst_definition.skills == ("/skills/procurement/",)
    assert "chart_params.md" in analyst_definition.system_prompt
    assert "前端 ECharts" in analyst_definition.system_prompt
    assert "禁止使用 matplotlib" in analyst_definition.system_prompt
    assert "不得写 `d[\\'key\\']`" in analyst_definition.system_prompt
    assert "read_file" in analyst_definition.system_prompt
    assert order_definition.skills == ("/skills/order/",)
    supplier_definition = next(
        definition for definition in definitions if definition.name == "supplier_manager"
    )
    assert supplier_definition.skills == ("/skills/supplier/",)
    assert order_definition.interrupt_on == {
        "create_order": {
            "allowed_decisions": ["approve", "reject"],
        },
        "update_order": {
            "allowed_decisions": ["approve", "reject"],
        },
    }
    assert supplier_definition.interrupt_on == {
        "create_supplier": {"allowed_decisions": ["approve", "reject"]},
    }


def test_subagent_interrupt_and_skills_remain_on_the_subagent() -> None:
    definition = SubagentDefinition(
        name="procurement_order",
        description="Collects missing fields.",
        system_prompt="Request human completion.",
        model=None,
        tools=("request_order_info",),
        interrupt_on={
            "request_order_info": {
                "allowed_decisions": ["respond"],
            }
        },
        skills=("/skills/order/",),
    )
    request_order_info = object()

    subagents = to_deep_agent_subagents(
        (definition,), {"request_order_info": request_order_info}
    )

    assert subagents == [
        {
            "name": "procurement_order",
            "description": "Collects missing fields.",
            "system_prompt": "Request human completion.",
            "tools": [request_order_info],
            "interrupt_on": {
                "request_order_info": {
                    "allowed_decisions": ["respond"],
                }
            },
            "skills": ["/skills/order/"],
        }
    ]


def test_local_shell_backend_adds_subagent_filesystem_middleware(tmp_path: Path) -> None:
    definition = SubagentDefinition(
        name="procurement_analyst",
        description="Analyzes procurement data.",
        system_prompt="Use execute for calculations.",
        model=None,
        tools=(),
        backend="local_shell",
    )

    subagents = to_deep_agent_subagents(
        (definition,),
        {},
        backend_root=tmp_path,
    )

    middleware = subagents[0]["middleware"]
    assert len(middleware) == 2
    assert isinstance(middleware[0], FilesystemMiddleware)
    assert isinstance(middleware[0].backend, LocalShellBackend)
    assert middleware[0].backend.cwd == tmp_path.resolve()
    assert isinstance(middleware[1], ToolCallLimitMiddleware)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("- not-a-mapping", "malformed.yaml"),
        (
            """name: sample
description: Investigates supplier and market questions.
""",
            "system_prompt",
        ),
        (
            """name: sample
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
tools: invalid_tool
""",
            "tools",
        ),
        (
            """name: sample
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
backend: remote_shell
""",
            "backend",
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
    valid_definition = """name: sample
description: Investigates supplier and market questions.
system_prompt: Gather evidence before responding.
"""
    write_definition(tmp_path, "first.yaml", valid_definition)
    write_definition(tmp_path, "second.yaml", valid_definition)

    with pytest.raises(SubagentConfigurationError, match="sample"):
        load_subagent_definitions(tmp_path)
