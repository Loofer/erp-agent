import pytest

from agent.memory.prompts import build_system_prompt
from agent.middlewares.request_context_prompt_middleware import (
    RequestContextPromptMiddleware,
)


def test_static_system_prompt_keeps_only_stable_main_agent_rules() -> None:
    prompt = build_system_prompt()

    assert "# Role & Scope" in prompt
    assert "human-in-the-loop" in prompt
    assert "/memory/AGENTS.md" in prompt
    assert "【委派子代理" not in prompt
    assert "## Request Context" not in prompt
    assert "## Retrieved Knowledge" not in prompt


def test_request_context_middleware_adds_identity_and_retrieval_context() -> None:
    middleware = RequestContextPromptMiddleware()
    captured = {}

    class Runtime:
        def __init__(self):
            self.context = {
                "user_id": "user-1",
                "username": "Test User",
                "current_time": "2026-08-05T00:00:00+00:00",
                "retrieval_context": '<retrieved_document source_id="parent-1">facts</retrieved_document>',
            }

    class Request:
        def __init__(self):
            self.runtime = Runtime()
            self.system_message = None

        def override(self, **kwargs):
            captured.update(kwargs)
            return self

    middleware.wrap_model_call(Request(), lambda request: request)

    content = "".join(block["text"] for block in captured["system_message"].content)
    assert "user-1" in content
    assert "Test User" in content
    assert "parent-1" in content
    assert "# Role & Scope" in content
    assert "untrusted reference content" in content


def test_request_context_middleware_preserves_initial_prompt_without_context() -> None:
    middleware = RequestContextPromptMiddleware()

    class Runtime:
        context = None

    class Request:
        def __init__(self):
            self.runtime = Runtime()
            self.system_message = object()
            self.overridden = False

        def override(self, **kwargs):
            self.overridden = True
            return self

    request = Request()

    assert middleware.wrap_model_call(request, lambda value: value) is request
    assert request.overridden is False


@pytest.mark.anyio
async def test_request_context_middleware_supports_async_model_calls() -> None:
    middleware = RequestContextPromptMiddleware()

    class Runtime:
        def __init__(self):
            self.context = {"user_id": "user-1", "username": "Test User"}

    class Request:
        def __init__(self):
            self.runtime = Runtime()

        def override(self, **kwargs):
            self.system_message = kwargs["system_message"]
            return self

    async def handler(request):
        return request

    result = await middleware.awrap_model_call(Request(), handler)
    assert "user-1" in result.system_message.content[0]["text"]
