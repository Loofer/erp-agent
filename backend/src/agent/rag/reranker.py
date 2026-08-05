"""Optional local Cross-Encoder reranker adapter."""

from __future__ import annotations

from collections.abc import Sequence


class FlagEmbeddingReranker:
    """Use FlagEmbedding's local reranker without making it a hard dependency."""

    def __init__(self, model_name: str, *, use_fp16: bool = True) -> None:
        try:
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError(
                "Local reranking requires the optional FlagEmbedding package."
            ) from exc
        self._reranker = FlagReranker(model_name, use_fp16=use_fp16)

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]:
        pairs = [[query, document] for document in documents]
        if not pairs:
            return []
        scores = self._reranker.compute_score(pairs, normalize=True)
        if isinstance(scores, (int, float)):
            return [float(scores)]
        return [float(score) for score in scores]
