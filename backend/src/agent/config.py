"""Environment-backed runtime configuration."""

from pydantic import AliasChoices, Field, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_BASE_URL = "http://47.92.108.163:8081"
DEFAULT_MODEL = "openai:gpt-4.1-mini"
DEFAULT_AGENT_ID = "motorparts-agent"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = Field(
        default=DEFAULT_API_BASE_URL,
        validation_alias=AliasChoices("MOTORPARTS_API_BASE_URL", "api_base_url"),
    )
    api_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MOTORPARTS_API_TOKEN", "api_token"),
    )
    base_url: str = Field(
        default="",
        validation_alias=AliasChoices("MOTORPARTS_MODEL_BASE_URL", "base_url"),
    )
    api_key: SecretStr = Field(
        default="",
        validation_alias=AliasChoices("MOTORPARTS_MODEL_API_KEY", "api_key"),
    )
    model: str = Field(
        default=DEFAULT_MODEL,
        validation_alias=AliasChoices("MOTORPARTS_AGENT_MODEL", "model"),
    )
    agent_id: str = Field(
        default=DEFAULT_AGENT_ID,
        validation_alias=AliasChoices("MOTORPARTS_AGENT_ID", "agent_id"),
    )
    database_url: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "database_url")
    )
    debug: bool = Field(
        validation_alias=AliasChoices("DEBUG_ENABLED", "debug")
    )
    @field_validator("api_token", mode="before")
    @classmethod
    def empty_api_token_is_none(cls, value: str | None) -> str | None:
        """Preserve the previous treatment of an empty optional API token."""
        return value or None


def load_settings() -> Settings:
    """Load validated settings from the environment and the local ``.env`` file."""
    return Settings()
