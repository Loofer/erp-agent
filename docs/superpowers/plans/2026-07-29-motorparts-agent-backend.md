# Motor Parts Agent Backend Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a runnable, tested backend skeleton with one read tool, one staged write tool, a HITL approval boundary, and an isolated future BI/Text2SQL subgraph boundary.

**Architecture:** A top-level LangGraph routes explicit caller intent to `data_query`, `create`, `research`, or `bi_query`. The only active contract operations are `getDashboard` (`GET`) and `create` (`POST /api/suppliers/create`); the POST is staged, interrupted for approval, and then sent only on an approved resume.

**Tech Stack:** Python 3.12, uv, FastAPI, LangGraph, Deep Agents, httpx, Pydantic, pytest, Ruff.

## Global Constraints

- Python version is `>=3.12`.
- Copy root `swagger.json` to `backend/openapi/swagger.json` without changing the contract.
- Expose only `getDashboard` as a read tool and `create` for supplier creation as a staged write tool.
- Any HTTP operation other than `GET` must be staged and human-approved before execution.
- `bi_query` is a standalone placeholder graph; it must not connect to a database or call an LLM.
- Tests must use `httpx.MockTransport`; no test may contact the configured public API host.
- Secrets come only from environment variables and are not committed.

---

### Task 1: Runnable Skeleton

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.gitignore`, `backend/README.md`, `backend/langgraph.json`
- Create: `backend/openapi/swagger.json`
- Create: `backend/src/motorparts_agent/{__init__,config,openapi,api_client,tools,actions,hitl,data_query,bi_query,research,graph,api}.py`
- Create: `backend/tests/{conftest,test_openapi,test_api_client,test_data_query,test_hitl,test_bi_query,test_graph,test_api}.py`

**Interfaces:**
- `load_operation_catalog(path: Path) -> dict[str, Operation]`
- `ApiClient.execute(operation: Operation, *, path_params: dict[str, object], query: dict[str, object], body: dict[str, object] | None) -> dict[str, object]`
- `PendingAction(operation_name: str, method: str, path: str, query: dict[str, object], body: dict[str, object] | None)`
- `build_graph(catalog: dict[str, Operation], client: ApiClient) -> CompiledStateGraph`

- [ ] **Step 1: Write failing tests**

```python
def test_catalog_classifies_dashboard_and_supplier_create(catalog: dict[str, Operation]) -> None:
    assert catalog["getDashboard"].is_mutation is False
    assert catalog["create"].is_mutation is True


def test_query_graph_rejects_supplier_create(catalog: dict[str, Operation]) -> None:
    assert build_data_query_graph(catalog).invoke({"operation_name": "create"})["error"] == "Mutation operations are not available in data_query."


def test_rejected_action_does_not_send_request(action: PendingAction, client: ApiClient) -> None:
    assert execute_after_approval(action, False, client)["status"] == "rejected"


def test_bi_graph_reports_not_configured() -> None:
    assert build_bi_query_graph().invoke({"question": "monthly purchasing trend"})["status"] == "not_configured"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -v`

Expected: FAIL because the package and test configuration do not exist.

- [ ] **Step 3: Implement the smallest complete skeleton**

```python
def stage_create_supplier(payload: dict[str, object], catalog: dict[str, Operation]) -> PendingAction:
    operation = catalog["create"]
    return PendingAction(operation.name, operation.method, operation.path, {}, payload)


def execute_query(state: QueryState, catalog: dict[str, Operation], client: ApiClient) -> QueryState:
    operation = catalog[state["operation_name"]]
    if operation.is_mutation:
        return {"error": "Mutation operations are not available in data_query."}
    return {"api_result": client.execute(operation, path_params={}, query={}, body=None)}
```

- [ ] **Step 4: Run focused and full verification**

Run: `uv run pytest -v && uv run ruff check .`

Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 5: Commit the initialized template**

Run:

```bash
git add backend docs/superpowers
git commit -m "feat: initialize motorparts agent backend"
```

Expected: one local commit containing the tested backend skeleton and its design records.

### Task 2: Reference Layout And Tool-Only Boundary

**Files:**
- Move: `backend/src/motorparts_agent/*` to `backend/src/api_view/*` and `backend/src/agent/*` by responsibility.
- Create: `backend/main.py`, `backend/bootstrap.py`, `backend/ARCH.md`, `backend/src/agent/tools/`, `backend/src/agent/workflows/`, `backend/src/agent/middlewares/`, `backend/src/agent/subagents/configs/`, `backend/skills/`, `backend/test/`, `backend/configs/`, `backend/data/`, `backend/logs/`, `backend/scripts/`.
- Delete: `backend/src/motorparts_agent/` after all imports and tests move.

**Interfaces:**
- `api_view.web_main.app` is the FastAPI application.
- `agent.main_agent.build_default_graph() -> CompiledStateGraph` builds the route graph.
- `agent.tools.erp_tools.get_dashboard(...)` and `stage_create_supplier(...)` are ordinary in-process tools; no module may import MCP packages or start an MCP server.
- `agent.workflows.bi_query.build_bi_query_graph() -> CompiledStateGraph` remains the future Text2SQL boundary.

- [ ] **Step 1: Write or migrate failing safety and layout tests**

```python
def test_direct_mutation_is_rejected_without_http_request() -> None:
    with pytest.raises(ApiClientError, match="must be staged and approved"):
        client.execute(create_operation, path_params={}, query={}, body=payload)


def test_staged_supplier_body_is_a_snapshot() -> None:
    source = {"supplierCode": "S-001", "name": "Acme"}
    action = stage_create_supplier(source, catalog)
    source["name"] = "Changed"
    assert action.body["name"] == "Acme"
```

- [ ] **Step 2: Run the tests to verify the current implementation fails**

Run: `uv run pytest -v`

Expected: the direct mutation and mutable-payload regression tests fail before the tool-only safety boundary exists.

- [ ] **Step 3: Move modules into the supplied layout and enforce the tool-only safety boundary**

```python
def execute(self, operation: Operation, **kwargs: object) -> dict[str, object]:
    if operation.is_mutation:
        raise ApiClientError("Mutation operations must be staged and approved.")
    return self._send(operation, **kwargs)
```

- [ ] **Step 4: Verify moved imports and complete suite**

Run: `uv run pytest -v && uv run ruff check .`

Expected: all tests pass, Ruff reports no violations, and `rg -n -i "mcp" backend` has no source-code matches.

### Task 3: Declarative Subagent Loader

**Files:**
- Create: `backend/src/agent/subagents/loader.py`, `backend/src/agent/subagents/configs/researcher.yaml`, `backend/tests/test_agent_loader.py`
- Modify: `backend/src/api_view/agent_loader.py`, `backend/src/agent/main_agent.py`, `backend/pyproject.toml`, `backend/README.md`

**Interfaces:**
- `SubagentDefinition(name: str, description: str, system_prompt: str, model: str | None, tools: tuple[str, ...])`
- `load_subagent_definitions(directory: Path) -> tuple[SubagentDefinition, ...]`
- `AgentLoader.load_subagents() -> tuple[SubagentDefinition, ...]`

- [ ] **Step 1: Write failing YAML-loader tests**

```python
def test_loader_reads_researcher_definition(config_directory: Path) -> None:
    definitions = load_subagent_definitions(config_directory)
    assert definitions[0].name == "researcher"
    assert definitions[0].tools == ("web_search",)


def test_loader_rejects_duplicate_subagent_names(config_directory: Path) -> None:
    with pytest.raises(SubagentConfigurationError, match="Duplicate"):
        load_subagent_definitions(config_directory)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_agent_loader.py -v`

Expected: FAIL because the YAML loader does not yet exist.

- [ ] **Step 3: Implement YAML parsing and integrate the application loader**

```python
def load_subagent_definitions(directory: Path) -> tuple[SubagentDefinition, ...]:
    documents = tuple(_load_one(path) for path in sorted(directory.glob("*.yaml")))
    _validate_unique_names(documents)
    return documents
```

- [ ] **Step 4: Run focused and full verification**

Run: `cmd /c "uv run pytest -v && uv run ruff check ."`

Expected: all tests pass and Ruff reports no violations.
