from agent.memory.prompts import build_system_prompt
from agent.middlewares import build_runtime_middlewares


def test_system_prompt_contains_operating_constraints() -> None:
    prompt = build_system_prompt()

    assert "汽车零部件采购助手" in prompt
    assert "ERP" in prompt
    assert "人工审批" in prompt


def test_runtime_middlewares_include_request_context_prompt() -> None:
    middlewares = build_runtime_middlewares()
    assert len(middlewares) == 1
    assert middlewares[0].__class__.__name__ == "RequestContextPromptMiddleware"
