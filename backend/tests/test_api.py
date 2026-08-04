from fastapi.testclient import TestClient


from api_view.web_main import app


def test_health_is_available_in_process() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_resume_endpoint_streams_service_events(monkeypatch) -> None:
    class FakeChatService:
        async def stream(self, **kwargs):
            yield {"event": "complete", "data": {"thread_id": "thread-1"}}

    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        FakeChatService,
    )

    response = TestClient(app).post(
        "/api/chat/thread-1/resume",
        json={"user_id": "user-1", "resume": {"supplement": "ABC"}},
    )

    assert response.status_code == 200
    assert "event: complete" in response.text


def test_application_lifespan_initializes_chat_service() -> None:
    with TestClient(app):
        assert app.state.chat_service is not None
