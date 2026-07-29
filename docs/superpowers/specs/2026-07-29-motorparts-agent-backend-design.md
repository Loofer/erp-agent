# Motor Parts Agent Backend Design

## Goal

Initialize a Python backend skeleton for an agent that serves the motor-parts procurement system described by the root `swagger.json` OpenAPI contract.

## Scope

The first increment provides an executable LangGraph project with four explicit routes:

- `data_query`: a deterministic subgraph that can invoke only read-only API tools.
- `create`: an agent route that prepares state-changing API requests and interrupts for human approval before an HTTP request is sent.
- `research`: a Deep Agents research route with a dedicated researcher subagent and an optional web-search provider.
- `bi_query`: a reserved subgraph boundary for a future Text2SQL/BI workflow; it returns a configured-not-yet response in this increment.

The checked contract contains 54 operations: 27 `GET` operations and 27 state-changing operations (`POST`, `PUT`, `PATCH`, and `DELETE`). The skeleton exposes exactly two operations: `getDashboard` as the representative read tool and `create` (`POST /api/suppliers/create`) as the representative mutation. The catalog still classifies all operations so later tools can be added safely. `GET` operations are query tools. Every other operation is a pending-action tool and requires explicit human approval.

## Architecture

`src/motorparts_agent/graph.py` owns the top-level `StateGraph` and routes a request through a structured classifier. It delegates data access to `data_query.py`, a focused subgraph that selects a cataloged read operation, validates tool arguments, executes the HTTP request, and returns normalized API data.

`create_agent.py` owns a write-only tool catalog. Its representative supplier-creation tool generates a `PendingAction` object rather than making an HTTP request. `hitl.py` calls LangGraph `interrupt` with the exact method, path, request body, and summary. A resumed run with `approved=True` invokes `ApiClient`; a rejected action returns a terminal response without sending a request.

`research.py` wraps a Deep Agent with a scoped researcher subagent. Web search is optional and disabled unless its provider configuration is present. Research has no access to the motor-parts write tools.

## Components

- `config.py`: typed environment configuration. `MOTORPARTS_API_BASE_URL` defaults to the OpenAPI server URL; no secret values are committed.
- `openapi.py`: validates and loads the copied OpenAPI document, derives immutable operation metadata, and separates read from state-changing operations.
- `api_client.py`: `httpx` client that interpolates validated path parameters, sends query parameters or JSON bodies, and raises domain-specific errors for non-success HTTP and API responses.
- `tools.py`: exposes only `get_dashboard` and `stage_create_supplier`. The operation catalog supports later safe expansion from `swagger.json`.
- `data_query.py`: a subgraph with `select_operation`, `execute_query`, and `summarize_result` nodes. It never calls a state-changing operation.
- `create_agent.py` and `hitl.py`: create/update/delete intent plus interrupt/resume approval boundary.
- `research.py`: isolated Deep Agents researcher configuration.
- `bi_query.py`: a standalone `StateGraph` factory reserved for future Text2SQL/BI implementation; it has no database connection or LLM in this increment.
- `api.py`: FastAPI health endpoint and a durable LangGraph-compatible request entry point.

## Data Flow

1. The HTTP API receives a request, `thread_id`, and optional runtime configuration.
2. The top-level graph selects `data_query`, `create`, or `research`.
3. `data_query` executes only `GET` metadata. `create` stages a mutation and yields an interrupt. `research` delegates to its researcher with no business-system write tools.
4. The caller resumes a create thread with `{ "approved": true }` or `{ "approved": false }`. Only an approved resume makes the configured HTTP request.
5. Responses preserve API payloads under typed state fields and return a user-facing summary separately.

## Error Handling And Safety

- Validate OpenAPI documents during startup; fail with a readable configuration error for missing or malformed contract files.
- Validate every operation name and required path/query/body argument before calling the API.
- Apply a bounded timeout to every HTTP request. Normalize transport failures, invalid JSON, non-2xx responses, and API-level error envelopes.
- Do not trust HTTP method alone outside the catalog: any operation not classified as `GET` is mutation-only and must pass HITL.
- Never include authorization tokens in logs, prompts, state snapshots, or committed files.
- Cap page size for list endpoints and cap serialized result size in agent context.

## Testing

- Unit-test OpenAPI classification, parameter rendering, client error normalization, and write-action staging without network access.
- Unit-test the data-query subgraph to prove it rejects mutation operations.
- Unit-test HITL approval and rejection: rejection sends no HTTP request, approval sends exactly one request with the staged method/path/body.
- Use `pytest` and `httpx.MockTransport`; no test contacts `47.92.108.163`.

## Out Of Scope

- Authentication design, frontend UI, persistence/checkpoint deployment, production web-search credentials, and automatic evaluation optimization. These can be layered onto this tested starter after the system authentication model and target deployment environment are known.
