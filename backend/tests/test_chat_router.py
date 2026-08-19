from typing import get_type_hints

from fastapi.testclient import TestClient

from api_view.chat_service import ChatService
from api_view.dependencies import get_chat_service
from api_view.web_main import app


def test_stream_endpoint_keeps_the_public_path(monkeypatch) -> None:
    class FakeChatService:
        async def stream(self, **kwargs):
            yield {"event": "complete", "data": {"thread_id": "thread-1"}}

    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        lambda: FakeChatService(),
    )

    response = TestClient(app).post(
        "/api/chat/stream",
        headers={
            "Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTEiLCJ1c2VybmFtZSI6IlRlc3QgVXNlciJ9."
        },
        json={"message": "status", "thread_id": "thread-1"},
    )

    assert response.status_code == 200
    assert "event: complete" in response.text


def test_history_endpoint_keeps_the_public_path(monkeypatch) -> None:
    class FakeChatService:
        async def list_sessions(self, user_id: str):
            assert user_id == "user-1"
            return [
                {
                    "thread_id": "thread-2",
                    "user_id": "user-1",
                    "agent_id": "motorparts-agent",
                    "created_at": "2026-08-01T00:00:00+00:00",
                    "updated_at": "2026-08-02T00:00:00+00:00",
                    "initial_prompt": "Show me open orders",
                    "message_count": 4,
                },
                {
                    "thread_id": "thread-1",
                    "user_id": "user-1",
                    "agent_id": "motorparts-agent",
                    "created_at": "2026-07-31T00:00:00+00:00",
                    "updated_at": "2026-08-01T00:00:00+00:00",
                    "initial_prompt": None,
                    "message_count": 2,
                },
            ]

    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        lambda: FakeChatService(),
    )

    response = TestClient(app).get(
        "/api/history",
        headers={
            "Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTEiLCJ1c2VybmFtZSI6IlRlc3QgVXNlciJ9."
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "sessions" in body
    assert [t["thread_id"] for t in body["sessions"]] == ["thread-2", "thread-1"]


def test_all_chat_routes_are_exposed_from_one_module() -> None:
    from api_view.chat import router

    routes = {(route.path, tuple(route.methods or ())) for route in router.routes}

    assert ("/api/chat/stream", ("POST",)) in routes
    assert ("/api/chat/{thread_id}/resume", ("POST",)) in routes
    assert ("/api/chat/{thread_id}", ("DELETE",)) in routes
    assert ("/api/history", ("GET",)) in routes


def test_delete_session_uses_the_authenticated_user(monkeypatch) -> None:
    class FakeChatService:
        async def delete_session(self, thread_id: str, user_id: str) -> bool:
            assert thread_id == "thread-1"
            assert user_id == "user-1"
            return True

    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        lambda: FakeChatService(),
    )

    response = TestClient(app).delete(
        "/api/chat/thread-1",
        headers={
            "Authorization": "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ1c2VyLTEiLCJ1c2VybmFtZSI6IlRlc3QgVXNlciJ9."
        },
    )

    assert response.status_code == 204


def test_all_chat_routes_declare_the_typed_chat_service_dependency() -> None:
    from api_view.chat import (
        chat_resume,
        chat_stream,
        delete_session,
        get_session_messages,
        list_history,
        router,
    )

    dependencies_by_path = {
        route.path: {dependency.call for dependency in route.dependant.dependencies}
        for route in router.routes
    }

    assert get_chat_service in dependencies_by_path["/api/chat/stream"]
    assert get_chat_service in dependencies_by_path["/api/chat/{thread_id}/resume"]
    assert get_chat_service in dependencies_by_path["/api/chat/{thread_id}"]
    assert get_chat_service in dependencies_by_path["/api/history"]
    assert get_type_hints(chat_stream)["service"] is ChatService
    assert get_type_hints(chat_resume)["service"] is ChatService
    assert get_type_hints(list_history)["service"] is ChatService
    assert get_type_hints(get_session_messages)["service"] is ChatService
    assert get_type_hints(delete_session)["service"] is ChatService
