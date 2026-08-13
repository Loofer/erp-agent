from typing import Self

from fastapi.testclient import TestClient

from api_view import web_main
from api_view.dependencies import get_chat_service

app = web_main.app


def test_health_is_available_in_process() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_resume_endpoint_streams_service_events(monkeypatch) -> None:
    received: dict[str, object] = {}

    class FakeChatService:
        async def stream(self, **kwargs):
            received.update(kwargs)
            yield {"event": "complete", "data": {"thread_id": "thread-1"}}

    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        FakeChatService,
    )

    response = TestClient(app).post(
        "/api/chat/thread-1/resume",
        headers={
            "Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTEiLCJ1c2VybmFtZSI6IlRlc3QgVXNlciJ9."
        },
        json={"resume": "创建人是 7"},
    )

    assert response.status_code == 200
    assert "event: complete" in response.text
    assert received["resume_data"] == "创建人是 7"


def test_application_lifespan_initializes_chat_service(monkeypatch) -> None:
    class FakeStore:
        @classmethod
        def from_conn_string(cls, _: str) -> "FakeStore":
            return cls()

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def setup(self) -> None:
            return None

    class FakeSaver:
        @classmethod
        def from_conn_string(cls, _: str) -> "FakeSaver":
            return cls()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def setup(self) -> None:
            return None

    class FakeConnection:
        @classmethod
        async def connect(cls, _: str, **kwargs: object) -> "FakeConnection":
            assert kwargs == {"autocommit": True}
            return cls()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class FakeConversationRepository:
        def __init__(self, connection: object) -> None:
            assert isinstance(connection, FakeConnection)

        async def setup(self) -> None:
            return None

    captured: dict[str, object] = {}

    monkeypatch.setattr(web_main, "PostgresStore", FakeStore)
    monkeypatch.setattr(web_main, "AsyncPostgresSaver", FakeSaver)
    monkeypatch.setattr(web_main, "AsyncConnection", FakeConnection)
    monkeypatch.setattr(web_main, "ConversationRepository", FakeConversationRepository)
    monkeypatch.setattr(web_main, "build_hybrid_retriever", lambda _: None)

    def fake_load_agent_graph(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(web_main, "load_agent_graph", fake_load_agent_graph)

    with TestClient(app):
        assert app.state.chat_service is not None
        assert "sandbox_backend" not in captured
