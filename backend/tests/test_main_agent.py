from typing import Any

from deepagents.backends import CompositeBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

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
    assert "interrupt_on" not in captured
    assert captured["memory"] == ["/memory/AGENTS.md", "/memories/AGENTS.md"]
    assert captured["skills"] == ["/skills/main/", "/skills/procurement/"]
    backend = captured["backend"]
    assert isinstance(backend, CompositeBackend)
    assert isinstance(backend.routes["/memories/"], StoreBackend)
    assert captured["permissions"]
    assert captured["checkpointer"] is None
    assert captured["store"] is None


def test_main_agent_uses_supplied_persistence_dependencies(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}
    supplied_checkpointer = object()
    supplied_store = InMemoryStore()

    def fake_create_deep_agent(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "agent.main_agent.deepagents.create_deep_agent", fake_create_deep_agent
    )

    create_main_agent(
        "test:model",
        subagents=(),
        checkpointer=supplied_checkpointer,
        store=supplied_store,
    )

    assert captured["checkpointer"] is supplied_checkpointer
    assert captured["store"] is supplied_store


def test_web_search_reports_missing_provider_configuration() -> None:
    result = web_search.invoke({"query": "supplier inventory news"})

    assert "not configured" in result.lower()


def test_deployment_entrypoint_loads_yaml_before_creating_main_agent(
    monkeypatch: Any,
) -> None:
    import agent.main_agent as main_agent_module

    expected_graph = object()
    expected_definitions = (
        SubagentDefinition(
            name="researcher",
            description="Researches evidence.",
            system_prompt="Research first.",
            model=None,
            tools=("web_search",),
        ),
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_agent_module,
        "load_subagent_definitions",
        lambda directory: expected_definitions,
    )

    def fake_create_main_agent(
        model: str,
        *,
        subagents: tuple[SubagentDefinition, ...],
        checkpointer: object | None = None,
        store: object | None = None,
    ) -> object:
        captured["model"] = model
        captured["subagents"] = subagents
        captured["checkpointer"] = checkpointer
        captured["store"] = store
        return expected_graph

    monkeypatch.setattr(main_agent_module, "create_main_agent", fake_create_main_agent)

    assert main_agent_module.load_agent_graph() is expected_graph
    assert captured["subagents"] == expected_definitions
    assert captured["checkpointer"] is None
    assert captured["store"] is None
