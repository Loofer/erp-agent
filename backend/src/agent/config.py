"""Environment-backed runtime configuration."""

import os
from dataclasses import dataclass

DEFAULT_API_BASE_URL = "http://47.92.108.163:8081"
DEFAULT_MODEL = "openai:gpt-4.1-mini"


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_token: str | None
    model: str


def load_settings() -> Settings:
    """Load configuration without reading or persisting secret files."""
    token = os.getenv("MOTORPARTS_API_TOKEN")
    return Settings(
        api_base_url=os.getenv("MOTORPARTS_API_BASE_URL", DEFAULT_API_BASE_URL),
        api_token=token or None,
        model=os.getenv("MOTORPARTS_AGENT_MODEL", DEFAULT_MODEL),
    )
