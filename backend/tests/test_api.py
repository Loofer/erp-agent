from fastapi.testclient import TestClient

from api_view.web_main import app


def test_health_is_available_in_process() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
