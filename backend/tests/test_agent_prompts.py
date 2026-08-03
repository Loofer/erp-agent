from agent.memory.prompts import build_system_prompt
from agent.middlewares import build_runtime_middlewares


def test_system_prompt_contains_operating_constraints() -> None:
    prompt = build_system_prompt()

    assert "motor-parts procurement assistant" in prompt
    assert "provided tools" in prompt
    assert "human approval" in prompt


def test_runtime_middlewares_are_an_explicit_empty_extension_boundary() -> None:
    assert build_runtime_middlewares() == []
