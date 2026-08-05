from agent.rag.hybrid_retriever import HybridRetriever, render_retrieval_context
from agent.rag.models import ChildChunk, ParentChunk
from agent.rag.query_rewriter import QueryVariants


class FixedRewriter:
    def rewrite(self, query: str) -> QueryVariants:
        return QueryVariants(query, "semantic brake", "P-100", "find compatible pad")


class FakeHybridStore:
    def __init__(self) -> None:
        self.parent = ParentChunk("parent-1", "doc-1", 0,
                                  "Pads fit the P-100 brake assembly.", 7,
                                  {"title": "Pads"})
        self.child = ChildChunk("child-1", "doc-1", "parent-1", 0, "P-100 pads", 2)
        self.calls: list[tuple[str, str]] = []

    def search_dense(self, query: str, limit: int):
        self.calls.append(("dense", query))
        return [(self.child, 0.9)]

    def search_sparse(self, query: str, limit: int):
        self.calls.append(("sparse", query))
        return [(self.child, 0.8)]

    def get_many(self, parent_ids: list[str]):
        return [self.parent] if self.parent.parent_id in parent_ids else []


def test_hybrid_retriever_searches_both_channels_for_original_and_rewrites() -> None:
    store = FakeHybridStore()
    result = HybridRetriever(search_store=store, query_rewriter=FixedRewriter()).retrieve(
        "find P-100 brake pads"
    )

    assert len(store.calls) == 8
    assert [candidate.parent.parent_id for candidate in result.context] == ["parent-1"]
    assert 'source_id="parent-1"' in render_retrieval_context(result.context)
