"""Deep Agents backend routes for bundled and durable user memory."""

import re
from pathlib import Path
from typing import TypedDict

from deepagents import FilesystemPermission
from deepagents.backends import (
    CompositeBackend,
    FilesystemBackend,
    StateBackend,
    StoreBackend,
)
from langgraph.runtime import Runtime

MEMORY_PATH = "/memory/AGENTS.md"
PERSISTENT_MEMORY_PATH = "/memories/AGENTS.md"
GLOBAL_SKILL_SOURCES = ["/skills/main/", "/skills/procurement/"]
_SAFE_NAMESPACE_COMPONENT = re.compile(r"^[A-Za-z0-9\-_.@+:~]+$")


class MemoryContext(TypedDict):
    """Immutable context required to scope durable agent memory."""

    user_id: str
    username: str
    agent_id: str
    current_time: str
    retrieval_context: str


def assistant_memory_namespace(
    runtime: Runtime[MemoryContext],
) -> tuple[str, str, str]:
    """Return an isolated persistent-memory namespace for the active user."""
    context = runtime.context
    user_id = context.get("user_id") if context else None
    agent_id = context.get("agent_id") if context else None
    if not isinstance(user_id, str) or not _SAFE_NAMESPACE_COMPONENT.fullmatch(user_id):
        raise ValueError("Memory persistence requires a valid user_id.")
    if not isinstance(agent_id, str) or not _SAFE_NAMESPACE_COMPONENT.fullmatch(agent_id):
        raise ValueError("Memory persistence requires a valid agent_id.")
    return (agent_id, user_id, "memories")


def build_agent_backend() -> CompositeBackend:
    """Expose bundled guidance and a durable, user-isolated memory route."""
    backend_root = Path(__file__).resolve().parents[3]
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/memory/": FilesystemBackend(
                root_dir=backend_root / "src" / "agent" / "memory",
                virtual_mode=True,
            ),
            "/memories/": StoreBackend(namespace=assistant_memory_namespace),
            "/skills/": FilesystemBackend(
                root_dir=backend_root / "skills",
                virtual_mode=True,
            ),
        },
    )


def build_runtime_permissions() -> list[FilesystemPermission]:
    """Keep bundled policy and skill files immutable to agent tool calls."""
    return [
        FilesystemPermission(
            operations=["write"],
            paths=["/memory/**", "/skills/**"],
            mode="deny",
        )
    ]
