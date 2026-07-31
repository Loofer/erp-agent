# PostgreSQL Persistence Design

## Goal

Replace the backend's SQLite and in-memory persistence with PostgreSQL, using
the configured `DATABASE_URL`, while preserving durable LangGraph recovery and
adding user-isolated long-term agent memory.

## Scope

The migration covers three persistence responsibilities:

1. LangGraph checkpoints and HITL resume state move from `AsyncSqliteSaver` to
   `AsyncPostgresSaver`.
2. Frontend display messages move from SQLite to a PostgreSQL repository.
3. Deep Agents receives a `PostgresStore` for durable files mounted at
   `/memories/`.

The existing bundled `/memory/AGENTS.md` and `/skills/` files remain read-only
filesystem content. This retains the deployed agent instructions on a fresh
database. `/memories/` is a distinct, writable, cross-thread memory area.

## Configuration

`agent.config.Settings` becomes a `pydantic_settings.BaseSettings` model with
`SettingsConfigDict(env_file=".env")`. It exposes `database_url`, populated from
the `DATABASE_URL` environment key, and retains the existing
`MOTORPARTS_API_BASE_URL`, `MOTORPARTS_API_TOKEN`, and
`MOTORPARTS_AGENT_MODEL` configuration fields. The obsolete
`MOTORPARTS_CHAT_DB_PATH` setting and SQLite data directory are removed.

Invalid or missing `DATABASE_URL` must cause startup configuration validation
to fail before the service accepts requests.

## Runtime Lifecycle

FastAPI's lifespan opens all persistence backends from the configured
`database_url`:

- `AsyncPostgresSaver` is initialized with `await setup()` and remains open for
  the application's lifespan.
- `PostgresStore` is initialized with `setup()` and remains open for the same
  lifespan.
- The display-message repository receives the asynchronous PostgreSQL
  connection exposed by the checkpointer and creates its table with
  `CREATE TABLE IF NOT EXISTS`.

The graph factory receives both the shared checkpointer and store. Shutdown
closes the resources in reverse order through their context managers.

## Agent Memory

The agent construction API accepts an optional LangGraph store. Production
wiring provides the shared `PostgresStore` to `create_deep_agent(store=store)`.
The composite backend adds a `/memories/` `StoreBackend` route.

The StoreBackend namespace is derived from the run context as
`("motorparts-agent", user_id, "memories")`. `ChatService` already passes a
context containing `user_id`; a `MemoryContext` schema makes that dependency
explicit. Therefore each user's long-term memory persists across that user's
threads but cannot be read by another user. The namespace factory must reject
missing or invalid user identifiers before StoreBackend performs persistence.

## Display Message Repository

`SQLiteDisplayMessageRepository` is replaced by
`PostgresDisplayMessageRepository`. It preserves the current public async API:

- `setup()` creates `display_messages`.
- `get(thread_id)` returns messages in `position` order.
- `save(thread_id, messages)` atomically replaces one thread's message list.

PostgreSQL parameter syntax is used, and writes remain committed before the
request lifecycle returns.

## Dependencies and Compatibility

The project removes `langgraph-checkpoint-sqlite` and adds the LangGraph
PostgreSQL checkpoint and store packages, `psycopg` with its binary extras, and
`pydantic-settings`. The lockfile is regenerated with `uv`.

No automatic data migration from existing local SQLite files is included:
they are development-local state and PostgreSQL starts with fresh tables. The
database URL already supplied in `.env` and `.env.example` is the sole runtime
connection configuration.

## Validation

Tests will cover:

- Pydantic loading of `DATABASE_URL` and validation when it is absent.
- Agent creation receiving the configured store and a user-isolated
  `/memories/` StoreBackend route.
- PostgreSQL repository query shape and ordered round-trip behavior through a
  test connection.
- Persistent checkpoint interruption and resume after reopening PostgreSQL.
- FastAPI lifespan wiring with both PostgreSQL persistence resources.

The complete backend test suite and Ruff will be run after the migration.
