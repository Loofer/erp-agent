from agent.rag.hybrid_retriever import RetrievalResult
from agent.rag.models import ParentChunk
from agent.rag.query_rewriter import QueryVariants
from agent.rag.retrieval import ParentCandidate
from agent.tools.knowledge_tools import build_knowledge_tools


class FakeRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, query: str) -> RetrievalResult:
        self.queries.append(query)
        parent = ParentChunk("p1", "d1", 0, "BP-100 fits MP-2024.", 4, {"title": "Fit"})
        candidate = ParentCandidate(parent, 0.4, ())
        return RetrievalResult(QueryVariants(query, "semantic", "keyword", "intent"), (candidate,))


def test_search_knowdge_returns_reranked_context() -> None:
    retriever = FakeRetriever()
    search = build_knowledge_tools(retriever)[0]

    result = search.invoke({"query": "compatibility"})

    assert result["status"] == "ok"
    assert result["results"][0]["source_id"] == "p1"
    assert retriever.queries == ["compatibility"]


def test_search_knowdge_handles_unconfigured_runtime() -> None:
    search = build_knowledge_tools(None)[0]

    result = search.invoke({"query": "anything"})

    assert result["status"] == "unavailable"
    assert result["results"] == []
