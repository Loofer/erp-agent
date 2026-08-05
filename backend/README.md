# Motorparts Agent Backend

Runnable backend skeleton for the motor-parts procurement agent.

## Development

```powershell
uv run pytest -v
uv run ruff check .
```

Set `DATABASE_URL` in `.env` before starting the API. It is loaded by Pydantic
Settings and is used for LangGraph checkpoints, frontend conversation metadata,
and long-term agent memory. Each user's long-term files are isolated beneath
the `/memories/` route; the bundled `/memory/AGENTS.md` and `/skills/` remain
read-only application guidance.

`MOTORPARTS_AGENT_ID` defaults to `motorparts-agent`. It is recorded with
`user_id` in the `t_deepagents_conversation` session table and scopes persistent memory.
`GET /api/history?user_id=<id>` returns that user's conversation `thread_ids`
in most-recently-active order.

`POST /api/chat/stream` accepts an optional `thread_id`. When it is absent, the
server creates a UUID and emits it first as a `conversation` SSE event. Each
subsequent `message_chunk` payload also includes `thread_id`.

The dashboard tool calls the ERP statistics endpoint directly. Supplier creation is staged as
a pending action and must be approved before an HTTP request is sent.

The Deep Agents runtime uses domain-organized in-process tools. The primary
Agent receives the read-only `get_dashboard` tool and the BI workflow.
`supplier_manager.yaml` receives supplier search, input collection, and creation
tools, while `procurement_order.yaml` receives order input collection and order
mutation tools. The `request_*_info` tools are `respond`-only ask-user
placeholders and do not call the ERP API; creation/update tools require
`approve` or `reject`. Other business-domain modules are intentionally empty
extension points until the relevant domain API is implemented.

Bundled memory and skills are exposed read-only through Deep Agents routes:
`/memory/AGENTS.md`, `/skills/main/`, `/skills/procurement/`, and the order
subagent's `/skills/order/` source. Persistent user memory is exposed through
`/memories/AGENTS.md` and is backed by PostgreSQL.
