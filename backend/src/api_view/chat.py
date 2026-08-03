"""Chat HTTP endpoints and Server-Sent Event encoding."""

import json
import os
import time
import uuid as _uuid_mod
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from .chat_persistence import ThreadInfo
from .dependencies import ChatServiceDependency

router = APIRouter()


# ---------------------------------------------------------------------------
# UUID v7 — time-ordered, no extra dependency
# ---------------------------------------------------------------------------


def _uuid7() -> str:
    """Return a time-ordered UUID version 7 string.

    Layout (128 bits):
        bits  0-47  : Unix timestamp in milliseconds
        bits 48-51  : version = 7
        bits 52-63  : rand_a  (12 random bits)
        bits 64-65  : variant = 0b10
        bits 66-127 : rand_b  (62 random bits)
    """
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")   # 80 random bits
    rand_a = (rand >> 68) & 0xFFF                  # top 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF          # bottom 62 bits
    value = (
        ((ms & 0xFFFF_FFFF_FFFF) << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return str(_uuid_mod.UUID(int=value))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    user_id: str


class ResumeRequest(BaseModel):
    user_id: str
    resume: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/chat/stream", tags=["chat"])
async def chat_stream(
    payload: ChatStreamRequest,
    service: ChatServiceDependency,
) -> EventSourceResponse:
    thread_id = payload.thread_id or _uuid7()
    return EventSourceResponse(
        _encode_sse_events(
            service.stream(
                message=payload.message,
                thread_id=thread_id,
                user_id=payload.user_id,
            )
        )
    )


@router.post("/api/chat/{thread_id}/resume", tags=["chat"])
async def chat_resume(
    thread_id: str,
    payload: ResumeRequest,
    service: ChatServiceDependency,
) -> EventSourceResponse:
    return EventSourceResponse(
        _encode_sse_events(
            service.stream(
                message=None,
                thread_id=thread_id,
                user_id=payload.user_id,
                resume_data=payload.resume,
            )
        )
    )


@router.get("/api/history", tags=["history"])
async def list_history(
    service: ChatServiceDependency,
    user_id: str = Query(min_length=1),
) -> dict[str, list[ThreadInfo]]:
    """Return the user's conversation threads with full metadata."""
    return {"threads": await service.list_threads(user_id)}


@router.get("/api/chat/{thread_id}/messages", tags=["chat"])
async def get_thread_messages(
    thread_id: str,
    service: ChatServiceDependency,
    user_id: str = Query(min_length=1),
) -> dict[str, list]:
    """Return the stored human/AI messages for an existing thread."""
    messages = await service.get_thread_messages(thread_id, user_id)
    return {"messages": messages}


# ---------------------------------------------------------------------------
# SSE encoding
# ---------------------------------------------------------------------------


async def _encode_sse_events(
    events: AsyncIterator[dict[str, object]],
) -> AsyncIterator[ServerSentEvent]:
    async for event in events:
        yield ServerSentEvent(
            event=str(event["event"]),
            data=json.dumps(event["data"], default=str),
        )
