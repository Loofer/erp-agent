"""Environment-backed runtime configuration."""

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_API_BASE_URL = "http://47.92.108.163:8081"
DEFAULT_MODEL = "openai:gpt-4.1-mini"
DEFAULT_AGENT_ID = "motorparts-agent"
DEFAULT_RAG_COLLECTION = "motorparts_knowledge"


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
    zilliz_uri: str = Field(
        default="",
        validation_alias=AliasChoices("ZILLIZ_URI", "zilliz_uri"),
    )
    zilliz_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ZILLIZ_TOKEN", "zilliz_token"),
    )
    milvus_collection: str = Field(
        default=DEFAULT_RAG_COLLECTION,
        validation_alias=AliasChoices("MILVUS_COLLECTION", "milvus_collection"),
    )
    embed_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("EMBED_MODEL", "embed_model"),
    )
    embed_dim: int = Field(
        default=1536,
        validation_alias=AliasChoices("EMBED_DIM", "embed_dim"),
    )
    rag_source_root: Path = Field(
        default=Path("doc"),
        validation_alias=AliasChoices("RAG_SOURCE_ROOT", "rag_source_root"),
    )
    parent_chunk_size: int = Field(
        default=1000,
        validation_alias=AliasChoices("PARENT_CHUNK_SIZE", "parent_chunk_size"),
    )
    parent_overlap: int = Field(
        default=120,
        validation_alias=AliasChoices("PARENT_OVERLAP", "parent_overlap"),
    )
    child_chunk_size: int = Field(
        default=240,
        validation_alias=AliasChoices("CHILD_CHUNK_SIZE", "child_chunk_size"),
    )
    child_overlap: int = Field(
        default=32,
        validation_alias=AliasChoices("CHILD_OVERLAP", "child_overlap"),
    )
    semantic_threshold: float = Field(
        default=0.72,
        validation_alias=AliasChoices("SEMANTIC_THRESHOLD", "semantic_threshold"),
    )
    reranker_model: str = Field(
        default="maidalun1020/bce-reranker-base_v1",
        validation_alias=AliasChoices("RERANKER_MODEL", "reranker_model"),
    )
    reranker_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("RERANKER_ENABLED", "reranker_enabled"),
    )
    @field_validator("api_token", mode="before")
    @classmethod
    def empty_api_token_is_none(cls, value: str | None) -> str | None:
        """Preserve the previous treatment of an empty optional API token."""
        return value or None


def load_settings() -> Settings:
    """Load validated settings from the environment and the local ``.env`` file."""
    return Settings()
