"""Conversation-history transport router boundary."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/history", tags=["history"])
