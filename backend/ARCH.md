# Backend Architecture

`main.py` and `bootstrap.py` expose the ASGI application. `src/api_view` owns
HTTP composition and routers. `src/agent` owns graph orchestration, direct API
tools, approval middleware, and explicit workflows. The tool boundary is
in-process Python; state-changing requests are staged and approved before the
client can send the representative supplier-create request.

`skills` contains versioned progressive-disclosure instructions for the current
procurement workflows. `test`, `configs`, `data`, `logs`, and `scripts` remain
reserved extension directories. Skill documents do not register tools; only
the explicit `agent.tools` registry can expose a capability to the runtime.

`agent.memory.runtime` mounts bundled `memory/` and `skills/` as read-only
filesystem sources and mounts `/memories/` as a PostgreSQL-backed `StoreBackend`.
The latter is scoped to the active user, so it persists across that user's
threads without crossing user boundaries. FastAPI's lifespan initializes an
`AsyncPostgresSaver` for LangGraph checkpoints and a `PostgresStore` for
durable memory from `DATABASE_URL`; it also stores frontend display messages in
the `t_deepagents_conversation` table in the same PostgreSQL database, scoped by
both `user_id` and `agent_id`. YAML subagents can select additional skill sources
and native HITL settings, which are validated before the Deep Agents graph is
constructed. Mutation and human-input tools are not registered on the primary
Agent; their YAML-owning subagents declare the corresponding `interrupt_on`
rules.
