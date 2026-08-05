from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api_view.auth import JwtIdentityMiddleware


def test_unsigned_jwt_username_claim_is_available_on_request_state() -> None:
    app = FastAPI()
    app.add_middleware(JwtIdentityMiddleware)

    @app.get("/api/identity")
    async def identity(request: Request):
        user = request.state.user
        return {"user_id": user.user_id, "user_name": user.user_name}

    token = (
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
        "eyJzdWIiOiJ1c2VyLTEiLCJ1c2VybmFtZSI6IlRlc3QgVXNlciJ9."
    )
    response = TestClient(app).get(
        "/api/identity", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1", "user_name": "Test User"}


def test_api_requests_without_bearer_token_are_rejected() -> None:
    app = FastAPI()
    app.add_middleware(JwtIdentityMiddleware)

    @app.get("/api/identity")
    async def identity():
        return {"ok": True}

    response = TestClient(app).get("/api/identity")

    assert response.status_code == 401
