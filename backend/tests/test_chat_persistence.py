import pytest
from backend.configs.settings import load_settings

from api_view.chat_persistence import SessionRepository


def test_load_settings_uses_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/chat")

    assert load_settings().database_url == "postgresql://user:pass@localhost:5432/chat"


class _FakeCursor:
    def __init__(self, owned: bool) -> None:
        self.owned = owned
        self.statements: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: str, _: tuple[str, ...]) -> None:
        self.statements.append(statement)

    async def fetchone(self) -> dict[str, bool]:
        return {"owned": self.owned}


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class _FakeConnection:
    def __init__(self, owned: bool) -> None:
        self.cursor_instance = _FakeCursor(owned)

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    def cursor(self, **_: object) -> _FakeCursor:
        return self.cursor_instance


@pytest.mark.anyio
async def test_delete_session_removes_parent_and_subagent_checkpoint_data() -> None:
    connection = _FakeConnection(owned=True)
    repository = SessionRepository(connection)  # type: ignore[arg-type]

    assert await repository.delete_session("thread-1", "user-1", "agent-1") is True

    statements = "\n".join(connection.cursor_instance.statements)
    assert "DELETE FROM session_events WHERE thread_id = %s" in statements
    assert "DELETE FROM checkpoint_writes WHERE thread_id = %s" in statements
    assert "DELETE FROM checkpoint_blobs WHERE thread_id = %s" in statements
    assert "DELETE FROM checkpoints WHERE thread_id = %s" in statements
    assert "checkpoint_ns" not in statements.split("DELETE FROM", 1)[1]


@pytest.mark.anyio
async def test_delete_session_does_not_delete_unowned_data() -> None:
    connection = _FakeConnection(owned=False)
    repository = SessionRepository(connection)  # type: ignore[arg-type]

    assert await repository.delete_session("thread-1", "other-user", "agent-1") is False
    assert len(connection.cursor_instance.statements) == 1
