"""Typed FastAPI dependencies for the HTTP transport layer."""

from typing import Annotated, cast

from fastapi import Depends, Request

from .chat_service import ChatService


def get_chat_service(request: Request) -> ChatService:
    """Resolve the application-scoped chat service with a concrete type."""
    return cast(ChatService, request.app.state.chat_service)


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
