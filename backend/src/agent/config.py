"""Environment-backed runtime configuration."""

import os
from dataclasses import dataclass

DEFAULT_API_BASE_URL = "http://47.92.108.163:8081"


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_token: str | None


def load_settings() -> Settings:
    """Load configuration without reading or persisting secret files."""
    token = os.getenv("MOTORPARTS_API_TOKEN")
    return Settings(
        api_base_url=os.getenv("MOTORPARTS_API_BASE_URL", DEFAULT_API_BASE_URL),
        api_token=token or None,
    )
