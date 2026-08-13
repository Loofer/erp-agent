from agent.memory.prompts import build_system_prompt
from agent.middlewares import RequestContextPromptMiddleware


def test_system_prompt_contains_operating_constraints() -> None:
    prompt = build_system_prompt()

    assert "汽车零部件采购助手" in prompt
    assert "ERP" in prompt
    assert "人工审批" in prompt
    assert "子代理文件交接" in prompt
    assert "read_file" in prompt


def test_runtime_middlewares_include_request_context_prompt() -> None:
    middleware = RequestContextPromptMiddleware()

    assert middleware.__class__.__name__ == "RequestContextPromptMiddleware"
