"""Temporary JWT request identity extraction for the chat API."""

import base64
import binascii
import json
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class RequestUser:
    """Authenticated identity available to API handlers for one request."""

    user_id: str
    user_name: str


class JwtIdentityMiddleware(BaseHTTPMiddleware):
    """Decode development JWT claims for API requests.

    This intentionally accepts unsigned development tokens. Replace the decoder
    with issuer, audience, expiry, and signature verification before deploying
    behind a real identity provider.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        try:
            request.state.user = _request_user_from_header(
                request.headers.get("Authorization")
            )
        except JwtIdentityError as exc:
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        return await call_next(request)


class JwtIdentityError(ValueError):
    """The request does not contain the required development JWT claims."""


def request_user(request: Request) -> RequestUser:
    """Return the identity supplied by ``JwtIdentityMiddleware``."""
    user = getattr(request.state, "user", None)
    if not isinstance(user, RequestUser):
        raise TypeError("JWT identity middleware is not configured.")
    return user


def _request_user_from_header(authorization: str | None) -> RequestUser:
    if not authorization:
        raise JwtIdentityError("Authorization bearer token is required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise JwtIdentityError("Authorization must use the Bearer scheme.")

    parts = token.split(".")
    if len(parts) != 3:
        raise JwtIdentityError("Authorization token is not a JWT.")
    try:
        payload = json.loads(_base64url_decode(parts[1]))
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise JwtIdentityError("Authorization token has an invalid payload.") from exc
    if not isinstance(payload, dict):
        raise JwtIdentityError("Authorization token payload must be an object.")

    user_id = payload.get("sub")
    user_name = payload.get("username")
    if not isinstance(user_id, str) or not user_id.strip():
        raise JwtIdentityError("Authorization token requires a string sub claim.")
    if not isinstance(user_name, str) or not user_name.strip():
        raise JwtIdentityError("Authorization token requires a string username claim.")
    return RequestUser(user_id=user_id, user_name=user_name)


def _base64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)
