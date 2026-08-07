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
from deepagents.backends.protocol import BackendProtocol
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore

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


def build_agent_backend(
        default_backend: BackendProtocol | None = None,
        store: BaseStore | None = None,
) -> CompositeBackend:
    """Expose sandbox execution, static files, and durable user memory."""
    backend_root = Path(__file__).resolve().parents[3]
    runtime_backend = default_backend or StateBackend()
    return CompositeBackend(
        default=runtime_backend,
        routes={
            "/sandbox/": runtime_backend,
            "/memory/": FilesystemBackend(
                root_dir=backend_root / "src" / "agent" / "memory",
                virtual_mode=True,
            ),
            "/memories/": StoreBackend(
                store=store,
                namespace=assistant_memory_namespace,
            ),
            "/skills/": FilesystemBackend(
                root_dir=backend_root / "skills",
                virtual_mode=True,
            ),
        },
    )


def build_runtime_permissions() -> list[FilesystemPermission]:
    """Keep bundled policy and skill files immutable to agent tool calls.
    - /memory/**、/skills/**：只可读，禁止写入/编辑/删除
    - /memories/**：用户长期记忆，允许读写
    """
    return [
        # 1. 禁止对静态共享资源执行任何写操作；读不受这条影响
        FilesystemPermission(
            operations=["write"],
            paths=["/memory/**", "/skills/**"],
            mode="deny",
        ),
        # 2. 用户记忆路径：允许 read + write
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/memories/**"],
            mode="allow",
        ),
        # 👉 没有加全局 deny，如果你需要严格白名单再追加下面这条
        # FilesystemPermission(
        #     operations=["read", "write"],
        #     paths=["/**"],
        #     mode="deny",
        # ),
    ]
