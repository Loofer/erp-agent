"""Request-scoped identity and retrieval context prompt middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse

from agent.memory.prompts import build_request_system_prompt


class RequestContextPromptMiddleware(AgentMiddleware[Any, Any, Any]):
    """Rebuild the system prompt from the current invocation context."""

    def wrap_model_call(self, request: ModelRequest[Any], handler: Any) -> ModelResponse[Any]:
        return handler(_request_with_context(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        """Apply the same prompt transformation on ``astream``/``ainvoke``."""
        return await handler(_request_with_context(request))


def _runtime_context(request: ModelRequest[Any]) -> dict[str, object]:
    runtime = request.runtime
    context = getattr(runtime, "context", None) if runtime else None
    return context if isinstance(context, dict) else {}


def _request_with_context(request: ModelRequest[Any]) -> ModelRequest[Any]:
    context = _runtime_context(request)
    if not context:
        return request
    prompt = build_request_system_prompt(
        user_id=_string(context.get("user_id")),
        user_name=_string(context.get("username")),
        current_time=_string(context.get("current_time")),
        retrieval_context=_string(context.get("retrieval_context")),
    )
    return request.override(system_message=append_to_system_message(None, prompt))


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
