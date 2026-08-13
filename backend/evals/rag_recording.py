"""RAG retriever wrapper that records evaluation diagnostics."""

from __future__ import annotations

from agent.rag.hybrid_retriever import HybridRetriever, RetrievalResult


class RecordingRetriever:
    def __init__(self, retriever: HybridRetriever | None) -> None:
        self.retriever = retriever
        self.last_result: RetrievalResult | None = None

    def retrieve(self, query: str) -> RetrievalResult:
        if self.retriever is None:
            raise RuntimeError("RAG retriever is unavailable")
        self.last_result = self.retriever.retrieve(query)
        return self.last_result

    def snapshot(self) -> dict[str, object]:
        result = self.last_result
        if result is None:
            return {"retrieved_ids": [], "retrieved_contexts": [], "query_variants": {}}
        return {
            "retrieved_ids": [item.parent.parent_id for item in result.context],
            "retrieved_contexts": [item.parent.content for item in result.context],
            "query_variants": {
                "original": result.variants.original,
                "semantic": result.variants.semantic,
                "keyword": result.variants.keyword,
                "intent": result.variants.intent,
            },
        }
