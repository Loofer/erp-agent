"""Deep Agents tools backed by the shared RAG retriever."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from ..rag.hybrid_retriever import HybridRetriever


def build_knowledge_tools(retriever: HybridRetriever | None) -> list[BaseTool]:
    """Build the primary-agent knowledge search tool around one retriever."""

    @tool("search_knowdge", parse_docstring=True)
    def search_knowdge(query: str) -> dict[str, object]:
        """Search the Motorparts knowledge base using hybrid retrieval and reranking.

        Args:
            query: A focused question or set of keywords to search for.
        """
        if retriever is None:
            return {
                "status": "unavailable",
                "message": "Knowledge base search is not configured.",
                "results": [],
            }
        if not query.strip():
            return {
                "status": "invalid_request",
                "message": "query must not be empty.",
                "results": [],
            }
        try:
            retrieval = retriever.retrieve(query.strip())
        except Exception:  # noqa: BLE001
            return {
                "status": "error",
                "message": "Knowledge base search failed.",
                "results": [],
            }
        return {
            "status": "ok",
            "query_variants": {
                "original": retrieval.variants.original,
                "semantic": retrieval.variants.semantic,
                "keyword": retrieval.variants.keyword,
                "intent": retrieval.variants.intent,
            },
            "results": [
                {
                    "source_id": candidate.parent.parent_id,
                    "title": candidate.parent.metadata.get("title", "Untitled"),
                    "content": candidate.parent.content,
                    "score": candidate.score,
                }
                for candidate in retrieval.context
            ],
        }

    return [search_knowdge]
