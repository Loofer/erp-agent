import pytest

from agent.middlewares.rag_context import RequestContextPromptMiddleware


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
