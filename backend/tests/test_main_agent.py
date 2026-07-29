from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from agent.main_agent import create_main_agent
from agent.subagents.loader import SubagentDefinition
from agent.tools.research_tools import web_search


def test_main_agent_uses_native_hitl_and_loaded_subagents(
    monkeypatch: Any,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_deep_agent(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "agent.main_agent.deepagents.create_deep_agent", fake_create_deep_agent
    )
    researcher = SubagentDefinition(
        name="researcher",
        description="Research supplier and market questions.",
        system_prompt="Gather evidence before responding.",
        model=None,
        tools=("web_search",),
    )

    graph = create_main_agent("test:model", subagents=(researcher,))

    assert graph is not None
    assert captured["model"] == "test:model"
    assert {tool.name for tool in captured["tools"]} == {
        "get_dashboard",
        "create_supplier",
        "run_bi_text2sql",
    }
    assert captured["subagents"] == [
        {
            "name": "researcher",
            "description": "Research supplier and market questions.",
            "system_prompt": "Gather evidence before responding.",
            "tools": [web_search],
        }
    ]
    assert captured["interrupt_on"] == {"create_supplier": True}
    assert isinstance(captured["checkpointer"], InMemorySaver)


def test_web_search_reports_missing_provider_configuration() -> None:
    result = web_search.invoke({"query": "supplier inventory news"})

    assert "not configured" in result.lower()
