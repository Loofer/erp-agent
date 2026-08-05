from pathlib import Path

import pytest

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
        ("procurement_analyst", ("get_dashboard", "run_bi_text2sql")),
        ("procurement_order", ("request_order_info", "create_order", "update_order")),
        (
            "supplier_manager",
            ("create_supplier", "search_suppliers", "request_supplier_info"),
        ),
    ]
    order_definition = next(
        definition for definition in definitions if definition.name == "procurement_order"
    )
    assert order_definition.skills == ("/skills/order/",)
    assert order_definition.interrupt_on == {
        "request_order_info": {
            "allowed_decisions": ["respond"],
        },
        "create_order": {
            "allowed_decisions": ["approve", "reject"],
        },
        "update_order": {
            "allowed_decisions": ["approve", "reject"],
        },
    }
    supplier_definition = next(
        definition for definition in definitions if definition.name == "supplier_manager"
    )
    assert supplier_definition.interrupt_on == {
        "request_supplier_info": {
            "allowed_decisions": ["respond"],
        },
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
