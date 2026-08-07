from typing import Any

from deepagents.backends import CompositeBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

from agent.main_agent import create_main_agent
from agent.subagents.loader import SubagentDefinition


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
    graph = create_main_agent("test:model", subagents=())

    assert graph is not None
    assert captured["model"] == "test:model"
    assert {tool.name for tool in captured["tools"]} == {"search_knowdge"}
    assert captured["subagents"] == []
    assert "interrupt_on" not in captured
    assert captured["memory"] == ["/memory/AGENTS.md", "/memories/preferences.md"]
    assert captured["skills"] == ["/skills/main/"]
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
    backend = captured["backend"]
    assert isinstance(backend, CompositeBackend)
    assert backend.routes["/memories/"]._store is supplied_store


def test_main_agent_uses_supplied_sandbox_as_default_backend(
    monkeypatch: Any,
) -> None:
    captured: dict[str, object] = {}
    sandbox_backend = object()

    def fake_create_deep_agent(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "agent.main_agent.deepagents.create_deep_agent", fake_create_deep_agent
    )

    create_main_agent(
        "test:model",
        subagents=(),
        sandbox_backend=sandbox_backend,
    )

    backend = captured["backend"]
    assert isinstance(backend, CompositeBackend)
    assert backend.default is sandbox_backend
    assert backend.routes["/sandbox/"] is sandbox_backend


def test_deployment_entrypoint_loads_yaml_before_creating_main_agent(
    monkeypatch: Any,
) -> None:
    import agent.main_agent as main_agent_module

    expected_graph = object()
    expected_definitions = (
        SubagentDefinition(
            name="supplier_manager",
            description="Manages suppliers.",
            system_prompt="Create suppliers after approval.",
            model=None,
            tools=("create_supplier",),
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
        rag_retriever: object | None = None,
        sandbox_backend: object | None = None,
    ) -> object:
        captured["model"] = model
        captured["subagents"] = subagents
        captured["checkpointer"] = checkpointer
        captured["store"] = store
        captured["rag_retriever"] = rag_retriever
        captured["sandbox_backend"] = sandbox_backend
        return expected_graph

    monkeypatch.setattr(main_agent_module, "create_main_agent", fake_create_main_agent)

    assert main_agent_module.load_agent_graph() is expected_graph
    assert captured["subagents"] == expected_definitions
    assert captured["checkpointer"] is None
    assert captured["store"] is None
    assert captured["sandbox_backend"] is None


def test_langgraph_dev_entrypoint_uses_default_persistence(monkeypatch: Any) -> None:
    import agent.main_agent as main_agent_module

    expected_graph = object()
    monkeypatch.setattr(main_agent_module, "load_agent_graph", lambda: expected_graph)

    assert main_agent_module.load_langgraph_dev_agent_graph() is expected_graph
