"""Chat HTTP endpoints and Server-Sent Event encoding."""

import json
import os
import time
import uuid as _uuid_mod
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from .auth import request_user
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
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = (rand >> 68) & 0xFFF  # top 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF  # bottom 62 bits
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


class ResumeRequest(BaseModel):
    resume: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/chat/stream", tags=["chat"])
async def chat_stream(
        payload: ChatStreamRequest,
        request: Request,
        service: ChatServiceDependency,
) -> EventSourceResponse:
    user = request_user(request)
    thread_id = payload.thread_id or _uuid7()
    return EventSourceResponse(
        _encode_sse_events(
            service.stream(
                message=payload.message,
                thread_id=thread_id,
                user_id=user.user_id,
                user_name=user.user_name,
            )
        )
    )


@router.post("/api/chat/{thread_id}/resume", tags=["chat"])
async def chat_resume(
        thread_id: str,
        payload: ResumeRequest,
        request: Request,
        service: ChatServiceDependency,
) -> EventSourceResponse:
    user = request_user(request)
    return EventSourceResponse(
        _encode_sse_events(
            service.stream(
                message=None,
                thread_id=thread_id,
                user_id=user.user_id,
                user_name=user.user_name,
                resume_data=payload.resume,
            )
        )
    )


@router.get("/api/history", tags=["history"])
async def list_history(
        request: Request,
        service: ChatServiceDependency,
) -> dict[str, list[ThreadInfo]]:
    """Return the user's conversation threads with full metadata."""
    return {"threads": await service.list_threads(request_user(request).user_id)}


@router.get("/api/chat/{thread_id}/messages", tags=["chat"])
async def get_thread_messages(
        thread_id: str,
        request: Request,
        service: ChatServiceDependency,
) -> dict[str, list]:
    """Return the stored human/AI messages for an existing thread."""
    messages = await service.get_thread_messages(thread_id, request_user(request).user_id)
    return {"messages": messages}


# ---------------------------------------------------------------------------
# SSE encoding
# ---------------------------------------------------------------------------


async def _encode_sse_events(
        events: AsyncIterator[dict[str, object]],
) -> AsyncIterator[ServerSentEvent]:
    """Encode service events as SSE, folding namespace/meta into the JSON body.

    SSE frames carry a single `data` field, so `namespace` and `meta` travel
    inside the payload rather than as sibling frame fields. `namespace` tells
    the client which (sub)agent produced the event: `[]` is the main agent.
    """
    async for event in events:
        payload = {
            "namespace": event.get("namespace", []),
            "meta": event.get("meta", {}),
            **_as_dict(event.get("data")),
        }
        yield ServerSentEvent(
            event=str(event["event"]),
            data=json.dumps(payload, ensure_ascii=False, default=str),
        )


def _as_dict(data: object) -> dict[str, Any]:
    return data if isinstance(data, dict) else {"value": data}
