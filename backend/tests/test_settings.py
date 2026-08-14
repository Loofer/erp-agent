from backend.configs.settings import load_settings


def test_motorparts_environment_variables_map_to_scoped_fields(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("MOTORPARTS_API_BASE_URL", "https://motorparts.example.test")
    monkeypatch.setenv("MOTORPARTS_API_TOKEN", "motorparts-token")
    monkeypatch.setenv("MOTORPARTS_MODEL_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("MOTORPARTS_MODEL_API_KEY", "model-key")
    monkeypatch.setenv("MOTORPARTS_AGENT_MODEL", "openai:test-model")
    monkeypatch.setenv("MOTORPARTS_AGENT_ID", "test-agent")

    settings = load_settings()

    assert settings.motorparts_api_base_url == "https://motorparts.example.test"
    assert settings.motorparts_api_token is not None
    assert settings.motorparts_api_token.get_secret_value() == "motorparts-token"
    assert settings.motorparts_model_base_url == "https://llm.example.test/v1"
    assert settings.motorparts_model_api_key.get_secret_value() == "model-key"
    assert settings.motorparts_agent_model == "openai:test-model"
    assert settings.motorparts_agent_id == "test-agent"
