"""Conversation history via LangGraph's checkpoint tables.

No separate session table — ownership and timing metadata are injected into
every checkpoint by ChatService via ``config["metadata"]`` and read back here.
"""

import asyncio
import json
from typing import TypedDict

from psycopg import AsyncConnection
from psycopg.rows import dict_row


class ThreadInfo(TypedDict):
    """Thread summary returned by the conversation history API."""

    thread_id: str
    user_id: str
    agent_id: str
    created_at: str | None       # ISO-8601; MIN(updated_at) across checkpoints
    updated_at: str | None       # ISO-8601; MAX(updated_at) across checkpoints
    initial_prompt: str | None   # First user message; present only in first run
    message_count: int           # Approximate: counts root-level checkpoints


# GIN index for fast metadata @> filtering.
# Without CONCURRENTLY so it can run inside the startup transaction.
_CREATE_GIN_INDEX = """
    CREATE INDEX IF NOT EXISTS checkpoints_metadata_gin_idx
        ON checkpoints USING gin(metadata jsonb_path_ops)
"""

_CREATE_ARTIFACTS_TABLE = """
    CREATE TABLE IF NOT EXISTS chat_artifacts (
        id BIGSERIAL PRIMARY KEY,
        thread_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        artifact_key TEXT NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(thread_id, artifact_type, artifact_key)
    )
"""
_CREATE_ARTIFACTS_INDEX = """
    CREATE INDEX IF NOT EXISTS chat_artifacts_thread_idx
        ON chat_artifacts(thread_id, created_at)
"""

# checkpoint_ns = '' limits to the top-level graph, excluding subgraph steps.
# MAX on ISO strings sorts chronologically. MAX(initial_prompt) skips NULLs,
# surfacing the value stored during the first run (later runs omit it).
_LIST_THREADS_SQL = """
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


class ConversationRepository:
    """Read-only view of conversation threads through LangGraph checkpoints."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        """Create a GIN index on checkpoints.metadata (idempotent)."""
        async with self._connection.cursor() as cur:
            await cur.execute(_CREATE_GIN_INDEX)
            await cur.execute(_CREATE_ARTIFACTS_TABLE)
            await cur.execute(_CREATE_ARTIFACTS_INDEX)

    async def save_artifact(
        self,
        thread_id: str,
        user_id: str,
        agent_id: str,
        artifact_type: str,
        artifact_key: str,
        payload: dict,
    ) -> None:
        """Upsert one analysis artifact without affecting chat execution."""
        async with self._lock, self._connection.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chat_artifacts
                    (thread_id, user_id, agent_id, artifact_type, artifact_key, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (thread_id, artifact_type, artifact_key)
                DO UPDATE SET payload = EXCLUDED.payload, created_at = NOW()
                """,
                (thread_id, user_id, agent_id, artifact_type, artifact_key,
                 json.dumps(payload, ensure_ascii=False)),
            )

    async def list_artifacts(self, thread_id: str, user_id: str) -> list[dict]:
        """Return artifacts belonging to the requested user/thread."""
        async with self._lock, self._connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT artifact_type, artifact_key, payload, created_at
                FROM chat_artifacts
                WHERE thread_id = %s AND user_id = %s
                ORDER BY created_at, id
                """,
                (thread_id, user_id),
            )
            rows = await cur.fetchall()
        return [
            {
                "type": row["artifact_type"],
                "key": row["artifact_key"],
                "payload": row["payload"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def list_threads(
        self, user_id: str, agent_id: str, *, limit: int = 50
    ) -> list[ThreadInfo]:
        """Return the user's threads ordered by most-recently-active."""
        async with self._lock, self._connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(_LIST_THREADS_SQL, (user_id, agent_id, limit))
            rows = await cur.fetchall()
        return [
            ThreadInfo(
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
