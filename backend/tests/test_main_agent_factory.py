import inspect

from agent.main_agent import create_main_agent


def test_main_agent_factory_does_not_expose_unused_api_client_parameter() -> None:
    assert "api_client" not in inspect.signature(create_main_agent).parameters
