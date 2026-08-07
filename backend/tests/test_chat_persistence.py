from backend.configs.settings import load_settings


def test_load_settings_uses_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/chat")

    assert load_settings().database_url == "postgresql://user:pass@localhost:5432/chat"
