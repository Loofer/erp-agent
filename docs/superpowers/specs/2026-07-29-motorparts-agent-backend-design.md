# Motor Parts Agent Backend Design

## Goal

Initialize a Python backend skeleton for an agent that serves the motor-parts procurement system described by the root `swagger.json` OpenAPI contract.

## Scope

The first increment provides an executable Deep Agents project. The primary
runtime receives one representative read tool, one human-approved supplier
creation tool, one BI adapter, and a declarative research subagent. The BI
adapter is the only dedicated LangGraph subgraph; it returns a
configured-not-yet response in this increment.

The checked contract contains 54 operations: 27 `GET` operations and 27 state-changing operations (`POST`, `PUT`, `PATCH`, and `DELETE`). The skeleton exposes exactly two operations: `getDashboard` as the representative read tool and `create` (`POST /api/suppliers/create`) as the representative mutation. The catalog still classifies all operations so later tools can be added safely. `GET` operations are query tools. Every other operation is a pending-action tool and requires explicit human approval.

## Architecture

`agent/main_agent.py` builds the primary runtime with `deepagents.create_deep_agent`. It owns the orchestration prompt, ordinary ERP tools, declarative YAML subagents, an `InMemorySaver` checkpointer for development, and Deep Agents-native `interrupt_on={"create_supplier": True}` HITL. It replaces the former top-level routing `StateGraph`.

`agent/tools/` contains ordinary LangChain `@tool` functions. `get_dashboard` performs the representative read request; `create_supplier` is the representative mutation, which Deep Agents interrupts before execution. The API client keeps raw mutation transport private to these tool closures. There is no custom approval graph or public approval-sender function.

`agent/subagents/loader.py` converts YAML definitions into Deep Agents subagent dictionaries, including the declared research `web_search` ordinary tool. Research has no ERP write tool.

## Components

- `src/api_view/`: FastAPI application composition, graph lifecycle loading, and request routers.
- `src/agent/`: the Deep Agents runtime boundary, configuration, schema, prompts, tool registry, and declarative subagents.
- `src/agent/tools/`: ordinary in-process HTTP tools. This replaces the reference structure's MCP client and MCP server directories; no MCP protocol or MCP dependency is used.
- `src/agent/tools/erp_tools.py`: representative `get_dashboard` and `create_supplier` Deep Agent tools.
- `src/agent/tools/bi_tools.py`: adapts the BI graph into one normal Deep Agent tool.
- `src/agent/workflows/bi_text2sql.py`: the only domain `StateGraph`, reserved for future Text2SQL/BI implementation; it has no database connection or LLM in this increment.
- `src/agent/subagents/loader.py`: parses and validates declarative YAML subagent definitions into immutable `SubagentDefinition` values. `api_view/agent_loader.py` loads those definitions before building the main graph; model/tool instantiation remains deferred.
- `src/agent/subagents/configs/researcher.yaml` and `skills/`: a starter deep-research specialist definition and progressive-disclosure operating instructions.

## Data Flow

1. The HTTP API receives a request, `thread_id`, and optional runtime configuration.
2. `AgentLoader` reads YAML subagent definitions and calls `create_deep_agent` with the configured model, ordinary tools, loaded subagents, skills, a checkpointer, and native `interrupt_on` rules.
3. The Deep Agent chooses read, research, create, or BI tools. BI is the only tool implemented as a dedicated LangGraph subgraph.
4. A `create_supplier` tool call interrupts through Deep Agents' HITL middleware. The caller resumes the same thread with `Command(resume={"decisions": [{"type": "approve"}]})`; only that approved decision invokes the configured HTTP request.
5. The runtime preserves tool results in its conversation state and returns the agent response separately.

## Error Handling And Safety

- Validate OpenAPI documents during startup; fail with a readable configuration error for missing or malformed contract files.
- Validate every operation name and required path/query/body argument before calling the API.
- Apply a bounded timeout to every HTTP request. Normalize transport failures, invalid JSON, non-2xx responses, and API-level error envelopes.
- Do not trust HTTP method alone outside the catalog: any operation not classified as `GET` is mutation-only and must pass HITL.
- Never include authorization tokens in logs, prompts, state snapshots, or committed files.
- Cap page size for list endpoints and cap serialized result size in agent context.

## Testing

- Unit-test OpenAPI classification, parameter rendering, client error normalization, and write-action staging without network access.
- Unit-test native Deep Agent construction: loaded subagents are passed in, `create_supplier` is declared in `interrupt_on`, and a checkpointer is configured.
- Unit-test ordinary tool closures and BI graph adapter without contacting external services.
- Use `pytest` and `httpx.MockTransport`; no test contacts `47.92.108.163`.
- Lock `deepagents>=0.6.12` and `langgraph>=1.2.8` in the backend's own uv environment; never rely on the root virtual environment.

## Out Of Scope

- Authentication design, frontend UI, persistence/checkpoint deployment, production web-search credentials, and automatic evaluation optimization. These can be layered onto this tested starter after the system authentication model and target deployment environment are known.

## Layout

The backend follows the supplied procurement-agent layout at the boundary level: `main.py` and `bootstrap.py` are startup points; `src/api_view` owns web transport; `src/agent` owns Deep Agents orchestration; `src/agent/tools` owns ordinary tools; `src/agent/workflows/bi_text2sql.py` owns the sole explicit LangGraph subgraph; `skills`, `test`, `configs`, `data`, `logs`, and `scripts` are reserved project areas. The reference `mcp_server` and `mcp_client.py` are deliberately omitted.
