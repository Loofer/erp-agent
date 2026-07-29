"""Chat transport router boundary."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/chat", tags=["chat"])
