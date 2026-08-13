"""Environment-backed runtime configuration."""

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MOTORPARTS_AGENT_MODEL = "gpt-5.4-mini"
DEFAULT_MOTORPARTS_AGENT_ID = "motorparts-agent"
DEFAULT_LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG_ENABLED", "debug"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    log_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOG_FILE", "log_file"),
    )
    motorparts_api_base_url: str = Field(
        default="",
        validation_alias="MOTORPARTS_API_BASE_URL",
    )
    motorparts_api_token: SecretStr | None = Field(
        default=None,
        validation_alias="MOTORPARTS_API_TOKEN",
    )
    motorparts_model_base_url: str = Field(
        default="",
        validation_alias="MOTORPARTS_MODEL_BASE_URL",
    )
    motorparts_model_api_key: SecretStr = Field(
        default="",
        validation_alias="MOTORPARTS_MODEL_API_KEY",
    )
    motorparts_agent_model: str = Field(
        default=DEFAULT_MOTORPARTS_AGENT_MODEL,
        validation_alias="MOTORPARTS_AGENT_MODEL",
    )
    motorparts_agent_id: str = Field(
        default=DEFAULT_MOTORPARTS_AGENT_ID,
        validation_alias="MOTORPARTS_AGENT_ID",
    )
    database_url: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "database_url")
    )
    langsmith_tracing: bool = Field(
        default=True,
        validation_alias=AliasChoices("LANGSMITH_TRACING", "langsmith_tracing"),
    )
    langsmith_endpoint: str = Field(
        default=DEFAULT_LANGSMITH_ENDPOINT,
        validation_alias=AliasChoices("LANGSMITH_ENDPOINT", "langsmith_endpoint"),
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGSMITH_API_KEY", "langsmith_api_key"),
    )
    langsmith_project: str = Field(
        default="erp-agent",
        validation_alias=AliasChoices("LANGSMITH_PROJECT", "langsmith_project"),
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
        default="",
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
        default=1200,
        validation_alias=AliasChoices("PARENT_CHUNK_SIZE", "parent_chunk_size"),
    )
    parent_overlap: int = Field(
        default=150,
        validation_alias=AliasChoices("PARENT_OVERLAP", "parent_overlap"),
    )
    child_chunk_size: int = Field(
        default=250,
        validation_alias=AliasChoices("CHILD_CHUNK_SIZE", "child_chunk_size"),
    )
    child_overlap: int = Field(
        default=50,
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
    ragas_judge_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("RAGAS_JUDGE_API_KEY", "ragas_judge_api_key"),
    )
    ragas_judge_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("RAGAS_JUDGE_BASE_URL", "ragas_judge_base_url"),
    )
    ragas_judge_model: str = Field(
        default="gpt-5.4-mini",
        validation_alias=AliasChoices("RAGAS_JUDGE_MODEL", "ragas_judge_model"),
    )
    ragas_judge_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices(
            "RAGAS_JUDGE_EMBEDDING_MODEL", "ragas_judge_embedding_model"
        ),
    )

    @field_validator("motorparts_api_token", mode="before")
    @classmethod
    def empty_api_token_is_none(cls, value: str | None) -> str | None:
        """Preserve the previous treatment of an empty optional API token."""
        return value or None


def load_settings() -> Settings:
    """Load validated settings from the environment and the local ``.env`` file."""
    return Settings()
