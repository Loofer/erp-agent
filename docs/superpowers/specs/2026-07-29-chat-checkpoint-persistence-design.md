# Chat Checkpoint Persistence Design

## Goal

Expose a server-sent-events chat API that persists LangGraph checkpoints and
display messages in SQLite, so an interrupted conversation can be resumed by
the same `thread_id` after the FastAPI process restarts.

## Scope

This increment replaces the main agent's process-local `InMemorySaver` with
LangGraph's SQLite checkpointer and implements the currently empty chat router.
It also introduces a small SQLite repository for frontend display messages.
The database is local process storage; it is not an authentication, multi-node,
or general memory solution.

## Architecture

`Settings` will expose a SQLite database path through an environment variable,
with a local runtime-data default that is excluded from version control.
FastAPI owns database lifecycle: startup opens and initializes one
`AsyncSqliteSaver`, shutdown closes it. The same saver instance is supplied to
every graph construction, so a configured `thread_id` addresses the same
checkpoint across requests and process restarts.

`agent.main_agent.create_main_agent` accepts a checkpointer dependency rather
than creating `InMemorySaver` itself. `AgentLoader` owns the cached graph and
provides a config containing both `thread_id` and `user_id`.

A dedicated repository owns a `display_messages` table with a stable
conversation ordering. It exposes only asynchronous `get` and replacement
`save` operations. The router and stream function do not contain SQL.

## API Contract

- `POST /api/chat/stream` accepts `message`, `thread_id`, and `user_id` in a
  JSON body and starts a new graph invocation for that thread.
- `POST /api/chat/{thread_id}/resume` accepts `user_id` and `resume` in a JSON
  body. It invokes the graph with `Command(resume=request.resume)` and the
  same configured `thread_id`.
- Both routes return `EventSourceResponse` with `text/event-stream` semantics.
- The stream emits `message_chunk` for graph messages, `graph_state` for state
  updates, `interrupt` for a LangGraph interrupt, `complete` after a normal
  graph completion, and `error` when invocation fails.
- Every normal completion and interrupt persists the accumulated display
  messages. The resume path reads the persisted messages before appending new
  output.

The stream is only valid when `message` is supplied for a new invocation or
`resume_data` is supplied for a resumed invocation. It will not silently run
with neither input.

## Data Flow

1. FastAPI startup opens the configured SQLite database, creates LangGraph's
   checkpoint tables, and initializes the display-message table.
2. A new chat request builds graph config with its `thread_id`, then streams
   the graph from a user message while collecting frontend-safe messages.
3. LangGraph writes checkpoints through `AsyncSqliteSaver`. If a native HITL
   interrupt occurs, the stream emits its payload and the message repository
   saves the display history.
4. A resume request loads display history, creates `Command(resume=...)`, and
   invokes the graph under the unchanged `thread_id`. The persisted checkpoint
   allows LangGraph to continue at the interrupted node even after restart.
5. The final display history is saved after normal completion or interruption.

## Error Handling And Safety

- Database paths are configuration, not request parameters.
- Database setup failures stop application startup rather than serving a route
  that cannot resume interrupted work.
- Stream exceptions produce an `error` event and are logged without leaking
  secrets or raw database internals to clients.
- Checkpoints are associated with the supplied `thread_id`; application-level
  authentication and authorization remain outside this increment.
- SQLite is scoped to one application instance. A later horizontally scaled
  deployment must use a shared production checkpointer backend.

## Testing

- Verify application lifecycle initializes the SQLite-backed dependencies.
- Verify display messages round-trip through a temporary SQLite database in
  deterministic order.
- Verify the agent factory receives the configured SQLite checkpointer rather
  than an in-memory saver.
- Verify initial and resume endpoints return an SSE response and pass the
  correct initial value or `Command(resume=...)` to the graph.
- Verify an interrupt persists display history and a later loader instance can
  read it from the same database.
- Tests use temporary files and fake graphs; no test contacts the ERP API or
  an LLM provider.

## Out Of Scope

- Migrating existing MongoDB data.
- User authentication, thread ownership enforcement, retention policies, and
  multi-process SQLite deployment.
- Frontend form rendering for HITL decisions.
