# Backend Agent Guide

## Project Overview

`motorparts-agent` is a motor-parts procurement assistant backend. It exposes a
streaming chat API (FastAPI + SSE) and runs an AI agent powered by the
**Deep Agents** framework on top of **LangGraph**. The agent connects to a
remote ERP API for procurement data and supports human-in-the-loop (HITL)
approval flows for state-changing actions.

All persistence (LangGraph checkpoints, conversation metadata, long-term agent
memory) is backed by **PostgreSQL**.

---

## Tech Stack

| Layer | Library / Version |
|---|---|
| Web framework | FastAPI ≥ 0.115 |
| AI runtime | `deepagents` ≥ 0.6.12 |
| Graph engine | LangGraph ≥ 1.2.8 |
| LLM client | `langchain-openai` ≥ 1.0 (OpenAI-compatible) |
| Checkpoints | `langgraph-checkpoint-postgres` ≥ 3.1.1 |
| DB driver | `psycopg[binary]` ≥ 3.3.4 |
| HTTP client | `httpx` ≥ 0.27 |
| Settings | `pydantic-settings` ≥ 2.14 |
| SSE transport | `sse-starlette` ≥ 3.4.6 |
| Python | ≥ 3.12 |
| Package manager | `uv` |

---

## Directory Structure

```
backend/
├── src/
│   ├── agent/                    # Core agent package
│   │   ├── config.py             # Pydantic Settings — all env vars
│   │   ├── main_agent.py         # Entry point: create_main_agent(), load_agent_graph()
│   │   ├── memory/
│   │   │   ├── AGENTS.md         # Bundled read-only agent guidance (exposed via /memory/)
│   │   │   ├── prompts.py        # System prompt composition
│   │   │   └── runtime.py        # Memory/skills backend, FilesystemPermission rules
│   │   ├── middlewares/
│   │   │   ├── __init__.py       # Middleware registration
│   │   │   └── config.py         # Middleware configuration
│   │   ├── subagents/
│   │   │   ├── loader.py         # YAML → SubagentDefinition → deepagents.SubAgent
│   │   │   └── configs/          # One YAML file per subagent
│   │   │       ├── procurement_analyst.yaml
│   │   │       ├── procurement_order.yaml
│   │   │       └── supplier_manager.yaml
│   │   ├── tools/
│   │   │   ├── __init__.py       # build_parent_tools(), build_subagent_only_tools()
│   │   │   ├── http_base.py      # ApiClient — all ERP HTTP calls go here
│   │   │   ├── hitl_tools.py     # Human-in-the-loop tool stubs
│   │   │   ├── statistics_tools.py
│   │   │   ├── suppliers_tools.py
│   │   │   ├── customers_tools.py
│   │   │   ├── inventory_tools.py
│   │   │   ├── logistics_tools.py
│   │   │   ├── orders_tools.py
│   │   │   ├── parts_tools.py
│   │   │   ├── bi_tools.py       # run_bi_text2sql workflow entry point
│   │   └── workflows/
│   │       └── bi_text2sql.py    # BI Text-to-SQL workflow
│   └── api_view/                 # FastAPI layer
│       ├── web_main.py           # App factory, lifespan (DB init, graph init)
│       ├── chat.py               # Router: /api/chat/stream, /api/chat/{id}/resume, etc.
│       ├── chat_service.py       # LangGraph stream → SSE event translation
│       ├── chat_persistence.py   # ConversationRepository — t_deepagents_conversation table
│       └── dependencies.py       # FastAPI dependency injection helpers
├── skills/                       # Bundled skill SKILL.md files (exposed read-only via /skills/)
│   ├── main/
│   │   ├── AGENTS.md             # Main agent top-level guidance
│   │   └── skill-management/SKILL.md
│   ├── order/
│   │   └── order-management/SKILL.md
│   └── procurement/
│       └── procurement-analysis/SKILL.md
├── tests/                        # pytest test suite
├── pyproject.toml
├── .env                          # Local secrets — never commit (see .env.example)
└── .env.example
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | **yes** | — | PostgreSQL connection string (psycopg3 format) |
| `MOTORPARTS_MODEL_API_KEY` | **yes** | — | LLM API key |
| `MOTORPARTS_MODEL_BASE_URL` | yes* | `""` | Base URL for OpenAI-compatible endpoint |
| `MOTORPARTS_AGENT_MODEL` | no | `openai:gpt-4.1-mini` | Model name in `provider:model` format |
| `MOTORPARTS_API_BASE_URL` | no | `http://47.92.108.163:8081` | ERP backend API base URL |
| `MOTORPARTS_API_TOKEN` | no | `None` | Bearer token for the ERP API (empty = no auth) |
| `MOTORPARTS_AGENT_ID` | no | `motorparts-agent` | Scopes persistent memory and conversation records |
| `DEBUG_ENABLED` | no | `False` | Enables Deep Agents debug logging |

> `*` Required when using a non-OpenAI endpoint (e.g., ModelScope, local Ollama).

---

## Development Commands

```powershell
# Run tests
uv run pytest -v

# Lint
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Start the API server (requires .env with DATABASE_URL)
uv run uvicorn src.api_view.web_main:app --reload --port 8000
```

---

## Architecture: Agent Runtime

### Primary Agent

Built in `main_agent.py::create_main_agent()`. Receives:
- Bundled system prompt from `memory/prompts.py`
- Memory routes: `/memory/AGENTS.md` (bundled guidance) and `/memories/AGENTS.md` (user-scoped durable)
- Skill sources: `/skills/main/` and `/skills/procurement/`

### Subagents

Defined declaratively in `subagents/configs/*.yaml`. Each YAML file specifies:
```yaml
name: <unique name>
description: <shown to primary agent for routing>
system_prompt: <agent instruction>
tools:           # list of tool names from the registry
  - tool_name
interrupt_on:    # optional HITL rules
  tool_name:
    allowed_decisions: [approve, reject]
skills:          # optional additional skill paths
  - /skills/order/
model: <optional override>  # omit to inherit parent model
```

**Active subagents:**

| Name | Role | HITL |
|---|---|---|
| `procurement_analyst` | Routes BI/dashboard queries | — |
| `procurement_order` | Collects and drafts procurement orders | `request_order_info` (respond); `create_order` / `update_order` (approve/reject) |
| `supplier_manager` | Stages supplier creation for approval | `request_supplier_info` (respond); `create_supplier` (approve/reject) |

### Tool Registration

Tools are registered in `tools/__init__.py`:
- `build_parent_tools(client)` → tools available to the **primary** agent
- `build_subagent_only_tools(client)` → tools only subagents can receive by name in YAML

**All HTTP calls must go through `ApiClient`** in `http_base.py`. The client sends
the method, path, query, and JSON body supplied by each tool and raises
`ApiClientError` on transport/HTTP/API errors.

To add a new tool:
1. Implement the tool function in the appropriate domain module (e.g., `orders_tools.py`)
2. Add it to `build_parent_tools()` or `build_subagent_only_tools()` in `tools/__init__.py`
4. Reference the tool name in the relevant subagent YAML if it's subagent-only

### Memory & Skills Backend

Three virtual filesystem routes are mounted via `CompositeBackend`:

| Route | Backend | Access |
|---|---|---|
| `/memory/` | `FilesystemBackend` → `src/agent/memory/` | Read-only (agent cannot write) |
| `/memories/` | `StoreBackend` → PostgreSQL (user + agent scoped) | Read/write |
| `/skills/` | `FilesystemBackend` → `backend/skills/` | Read-only (agent cannot write) |

The `/memory/` and `/skills/` routes are **write-denied** by `build_runtime_permissions()`.
The agent writes durable notes to `/memories/AGENTS.md` only.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat/stream` | Start or continue a conversation (SSE) |
| `POST` | `/api/chat/{thread_id}/resume` | Resume after a HITL interrupt (SSE) |
| `GET` | `/api/history?user_id=<id>` | List a user's conversation threads |
| `GET` | `/api/chat/{thread_id}/messages?user_id=<id>` | Get messages for a thread |
| `GET` | `/health` | Liveness probe |

### SSE Event Types

| Event | Payload | Notes |
|---|---|---|
| `conversation` | `{ thread_id }` | Always first; signals the active thread ID |
| `message_chunk` | `{ content, thread_id, ... }` | Streaming text; `content` may be `string` or `ContentBlock[]` |
| `complete` | `{ thread_id }` | Stream finished normally |
| `error` | `{ error }` | Stream finished with error |
| `interrupt` | `{ thread_id, tool_name, ... }` | HITL pause; resume via `/api/chat/{id}/resume` |

---

## Testing

Tests live in `backend/tests/`. Run with `uv run pytest -v`.

- `conftest.py` sets up shared fixtures (DB mocks, agent mocks, test client)
- Domain tool tests: `test_domain_tools.py`
- Agent tests: `test_main_agent.py`, `test_main_agent_factory.py`
- API tests: `test_api.py`, `test_chat_router.py`, `test_chat_service.py`
- Persistence tests: `test_chat_checkpoint.py`, `test_chat_persistence.py`
- Subagent loader tests: `test_subagent_loader.py`
- Skill layout tests: `test_skill_layout.py`

---

## Skills System

`skills-lock.json` at the **project root** is the lock file for remotely sourced
skills (similar to `package-lock.json`). It is **committed to git** and pins
resolved hashes for each skill source. Do not edit it manually.

Bundled skill files in `backend/skills/` are the runtime copies and are also
committed. They are exposed read-only to the agent via the `/skills/` backend route.

---

## Key Conventions

- **Settings**: always read via `load_settings()` — never access `os.environ` directly.
- **HTTP**: all ERP API calls go through `ApiClient.execute()`. Never use `httpx` directly in tool code.
- **Mutations**: only `create_supplier` is an active mutation. Any new mutation requires an explicit HITL `interrupt_on` rule in the subagent YAML.
- **Subagents**: add to `subagents/configs/` as a new YAML file. The loader auto-discovers all `*.yaml` files in that directory.
- **Tool naming**: tool names in YAML must exactly match the `name` attribute on the `@tool`-decorated function.
- **Line length**: 88 chars (ruff default). Target Python 3.12.
---

## Uncertainties / Suggestions

- `MOTORPARTS_API_TOKEN` support in `ApiClient` — the token is loaded into settings
  but it is not clear whether `ApiClient` currently injects it as a Bearer header.
  Verify `http_base.py` passes auth headers when the token is set.
- `bi_text2sql.py` workflow — the BI endpoint URL and any required credentials are
  not yet documented. Add the relevant env vars to `.env.example` when configured.
- User authentication is not implemented. `user_id` is passed from the frontend
  as a plain string. Production deployments should validate it via middleware.
