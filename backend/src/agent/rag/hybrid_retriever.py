"""Hybrid dense/BM25 RAG retrieval using rewrites, RRF, and reranking."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Protocol

from .models import ChildChunk
from .query_rewriter import QueryRewriter, QueryVariants
from .rag_store import ParentStore
from .retrieval import (
    ChildSearchHit,
    ParentCandidate,
    RerankerProvider,
    expand_parents,
    rerank_parents,
    weighted_rrf,
)


class HybridSearchStore(ParentStore, Protocol):
    def search_dense(self, query: str, limit: int) -> list[tuple[ChildChunk, float]]: ...

    def search_sparse(self, query: str, limit: int) -> list[tuple[ChildChunk, float]]: ...


@dataclass(frozen=True)
class RetrievalConfig:
    per_channel_limit: int = 20
    fused_child_limit: int = 30
    parent_limit: int = 12
    context_limit: int = 3
    rrf_constant: int = 60


@dataclass(frozen=True)
class RetrievalResult:
    variants: QueryVariants
    context: tuple[ParentCandidate, ...]


class HybridRetriever:
    _QUERY_WEIGHTS: ClassVar[dict[str, float]] = {
        "original": 1.0,
        "semantic": 0.8,
        "keyword": 0.9,
        "intent": 0.85,
    }

    def __init__(self, *, search_store: HybridSearchStore,
                 query_rewriter: QueryRewriter,
                 reranker: RerankerProvider | None = None,
                 config: RetrievalConfig | None = None) -> None:
        self._search_store = search_store
        self._query_rewriter = query_rewriter
        self._reranker = reranker
        self._config = config or RetrievalConfig()

    def retrieve(self, query: str) -> RetrievalResult:
        variants = self._query_rewriter.rewrite(query)
        rankings: list[list[ChildSearchHit]] = []
        for query_type, rewritten_query in variants.items():
            rankings.append(self._search_channel(rewritten_query, query_type, "dense"))
            rankings.append(self._search_channel(rewritten_query, query_type, "sparse"))
        fused = weighted_rrf(rankings, self._QUERY_WEIGHTS,
                             constant=self._config.rrf_constant,
                             limit=self._config.fused_child_limit)
        candidates = expand_parents(fused, self._search_store, limit=self._config.parent_limit)
        context = rerank_parents(query, candidates, self._reranker, limit=self._config.context_limit)
        return RetrievalResult(variants=variants, context=tuple(context))

    def _search_channel(self, query: str, query_type: str, channel: str) -> list[ChildSearchHit]:
        search = self._search_store.search_dense if channel == "dense" else self._search_store.search_sparse
        return [ChildSearchHit(child, rank, score, query_type, channel)
                for rank, (child, score) in enumerate(
                    search(query, self._config.per_channel_limit), start=1)]


def render_retrieval_context(candidates: Sequence[ParentCandidate]) -> str:
    """Render untrusted retrieved text as clearly delimited model context."""
    return "\n\n".join(
        "<retrieved_document "
        f'source_id="{candidate.parent.parent_id}" '
        f'title="{candidate.parent.metadata.get("title", "Untitled")}">\n'
        f"{candidate.parent.content}\n</retrieved_document>"
        for candidate in candidates
    )
