"""Session metadata and user-visible event history persistence."""

import asyncio
from datetime import UTC, datetime
from typing import TypedDict

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class SessionInfo(TypedDict):
    """Session summary returned by the session history API."""

    thread_id: str
    user_id: str
    agent_id: str
    created_at: str | None
    updated_at: str | None
    initial_prompt: str | None
    message_count: int


class SessionEvent(TypedDict):
    """One durable, user-visible event emitted during a session turn."""

    event_id: str
    thread_id: str
    turn_id: str
    sequence: int
    event_type: str
    user_id: str
    agent_id: str
    source: str
    namespace: list[str]
    agent_name: str | None
    message_id: str | None
    tool_call_id: str | None
    tool_name: str | None
    payload: dict[str, object]
    created_at: datetime


_CREATE_CHECKPOINT_METADATA_INDEX = """
    CREATE INDEX IF NOT EXISTS checkpoints_metadata_gin_idx
        ON checkpoints USING gin(metadata jsonb_path_ops)
"""

_CREATE_SESSION_EVENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS session_events (
        event_id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        user_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        source TEXT NOT NULL,
        namespace JSONB NOT NULL DEFAULT '[]'::jsonb,
        agent_name TEXT,
        message_id TEXT,
        tool_call_id TEXT,
        tool_name TEXT,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE (thread_id, turn_id, sequence)
    )
"""

_CREATE_SESSION_EVENT_INDEXES = (
    (
        "CREATE INDEX IF NOT EXISTS session_events_thread_sequence_idx "
        "ON session_events (thread_id, created_at, sequence)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS session_events_thread_tool_call_idx "
        "ON session_events (thread_id, tool_call_id)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS session_events_owner_idx "
        "ON session_events (thread_id, user_id, agent_id)"
    ),
)

_LIST_SESSIONS_SQL = """
    SELECT
        thread_id,
        MAX(metadata->>'user_id')        AS user_id,
        MAX(metadata->>'agent_id')       AS agent_id,
        MIN(metadata->>'updated_at')     AS created_at,
        MAX(metadata->>'updated_at')     AS updated_at,
        MAX(metadata->>'initial_prompt') AS initial_prompt,
        COUNT(*)::int                    AS message_count
    FROM   checkpoints
    WHERE  metadata @> jsonb_build_object('user_id', %s::text, 'agent_id', %s::text)
      AND  checkpoint_ns = ''
    GROUP  BY thread_id
    ORDER  BY MAX(metadata->>'updated_at') DESC
    LIMIT  %s
"""

_INSERT_SESSION_EVENT_SQL = """
    INSERT INTO session_events (
        event_id, thread_id, turn_id, sequence, event_type, user_id, agent_id,
        source, namespace, agent_name, message_id, tool_call_id, tool_name,
        payload, created_at
    ) VALUES (
        %(event_id)s, %(thread_id)s, %(turn_id)s, %(sequence)s, %(event_type)s,
        %(user_id)s, %(agent_id)s, %(source)s, %(namespace)s, %(agent_name)s,
        %(message_id)s, %(tool_call_id)s, %(tool_name)s, %(payload)s,
        %(created_at)s
    ) ON CONFLICT DO NOTHING
"""

_GET_SESSION_EVENTS_SQL = """
    SELECT
        event_id, thread_id, turn_id, sequence, event_type, source, namespace,
        agent_name, message_id, tool_call_id, tool_name, payload, created_at
    FROM session_events
    WHERE thread_id = %s AND user_id = %s AND agent_id = %s
    ORDER BY created_at, sequence, event_id
"""

_SESSION_OWNED_SQL = """
    SELECT EXISTS(
        SELECT 1
        FROM checkpoints
        WHERE thread_id = %s
          AND checkpoint_ns = ''
          AND metadata @> jsonb_build_object('user_id', %s::text, 'agent_id', %s::text)
    ) AS owned
"""


class SessionRepository:
    """Session metadata and append-only event-log access through PostgreSQL."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        """Create idempotent session metadata indexes and event-log storage."""
        async with self._connection.cursor() as cur:
            await cur.execute(_CREATE_CHECKPOINT_METADATA_INDEX)
            await cur.execute(_CREATE_SESSION_EVENTS_TABLE)
            for statement in _CREATE_SESSION_EVENT_INDEXES:
                await cur.execute(statement)

    async def list_sessions(
        self, user_id: str, agent_id: str, *, limit: int = 50
    ) -> list[SessionInfo]:
        """Return the user's sessions ordered by most-recent activity."""
        async with self._lock, self._connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(_LIST_SESSIONS_SQL, (user_id, agent_id, limit))
            rows = await cur.fetchall()
        return [
            SessionInfo(
                thread_id=row["thread_id"],
                user_id=row["user_id"],
                agent_id=row["agent_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                initial_prompt=row["initial_prompt"],
                message_count=row["message_count"],
            )
            for row in rows
        ]

    async def append_events(self, events: list[SessionEvent]) -> None:
        """Append one ordered turn batch without rewriting prior session history."""
        if not events:
            return
        rows = [
            {
                **event,
                "namespace": Jsonb(event["namespace"]),
                "payload": Jsonb(event["payload"]),
                "created_at": event["created_at"].astimezone(UTC),
            }
            for event in events
        ]
        async with self._lock, self._connection.cursor() as cur:
            await cur.executemany(_INSERT_SESSION_EVENT_SQL, rows)

    async def get_session_events(
        self, thread_id: str, user_id: str, agent_id: str
    ) -> list[dict[str, object]]:
        """Return durable UI events only when the requesting user owns the session."""
        async with self._lock, self._connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(_GET_SESSION_EVENTS_SQL, (thread_id, user_id, agent_id))
            rows = await cur.fetchall()
        return [
            {
                **row,
                "namespace": row["namespace"] if isinstance(row["namespace"], list) else [],
                "payload": row["payload"] if isinstance(row["payload"], dict) else {},
            }
            for row in rows
        ]

    async def owns_session(self, thread_id: str, user_id: str, agent_id: str) -> bool:
        """Check checkpoint ownership before falling back to checkpoint history."""
        async with self._lock, self._connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(_SESSION_OWNED_SQL, (thread_id, user_id, agent_id))
            row = await cur.fetchone()
        return bool(row and row["owned"])
