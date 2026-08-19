from agent.memory.prompts import build_system_prompt
from agent.middlewares import RequestContextPromptMiddleware


def test_system_prompt_contains_operating_constraints() -> None:
    prompt = build_system_prompt()

    assert "motor-parts procurement assistant" in prompt
    assert "Motorparts facts" in prompt
    assert "human-in-the-loop" in prompt
    assert "Only call `read_file`" in prompt
    assert "/analysis/report_*.md" in prompt
    assert "/sandbox/procurement_analyst_report_*.md" in prompt
    assert "read_file" in prompt


def test_runtime_middlewares_include_request_context_prompt() -> None:
    middleware = RequestContextPromptMiddleware()

    assert middleware.__class__.__name__ == "RequestContextPromptMiddleware"
