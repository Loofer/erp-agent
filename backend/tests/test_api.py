from fastapi.testclient import TestClient

from api_view.dependencies import get_chat_service
from api_view.web_main import app


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


def test_application_lifespan_initializes_chat_service() -> None:
    with TestClient(app):
        assert app.state.chat_service is not None
