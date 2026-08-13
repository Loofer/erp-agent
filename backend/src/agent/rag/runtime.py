"""Build the optional request-time RAG service from application settings."""

from __future__ import annotations

from backend.configs.settings import Settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .hybrid_retriever import HybridRetriever
from .milvus_store import MilvusChunkStore
from .providers import OpenAIEmbeddingProvider
from .query_rewriter import JsonQueryRewriter
from .reranker import FlagEmbeddingReranker


def build_hybrid_retriever(settings: Settings) -> HybridRetriever | None:
    """Create a Zilliz retriever only when non-placeholder credentials exist."""
    if not _configured(settings.zilliz_uri, settings.zilliz_token):
        return None
    embedding_model = OpenAIEmbeddings(
        model=settings.embed_model,
        dimensions=settings.embed_dim,
        api_key=settings.motorparts_model_api_key,
        base_url=settings.motorparts_model_base_url or None,
    )
    provider = OpenAIEmbeddingProvider(embedding_model)
    store = MilvusChunkStore(
        uri=settings.zilliz_uri,
        token=settings.zilliz_token.get_secret_value(),
        collection_name=settings.milvus_collection,
        embedding_provider=provider,
        embedding_dimension=settings.embed_dim,
    )
    store.ensure_collection()
    rewrite_model = ChatOpenAI(
        model=settings.motorparts_agent_model,
        api_key=settings.motorparts_model_api_key,
        base_url=settings.motorparts_model_base_url or None,
    )
    reranker = None
    if settings.reranker_enabled:
        try:
            reranker = FlagEmbeddingReranker(settings.reranker_model)
        except RuntimeError:
            # Keep dense/sparse retrieval available when the optional local model
            # package or model weights are not installed on this process.
            reranker = None
    return HybridRetriever(
        search_store=store,
        query_rewriter=JsonQueryRewriter(rewrite_model),
        reranker=reranker,
    )


def _configured(uri: str, token: object) -> bool:
    if not isinstance(token, str):
        token = getattr(token, "get_secret_value", lambda: "")()
    return bool(uri and token and uri != "xxx" and token != "xxx")
