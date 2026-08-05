from agent.rag.models import ChildChunk, ParentChunk
from agent.rag.rag_store import InMemoryParentStore
from agent.rag.retrieval import (
    ChildSearchHit,
    expand_parents,
    rerank_parents,
    weighted_rrf,
)


def _child(child_id: str, parent_id: str) -> ChildChunk:
    return ChildChunk(child_id, "doc-1", parent_id, 0, child_id, 1)


def test_weighted_rrf_prefers_original_query_and_deduplicates_children() -> None:
    original = _child("child-original", "parent-1")
    rewritten = _child("child-rewritten", "parent-2")
    result = weighted_rrf(
        [
            [ChildSearchHit(original, 1, 0.9, "original", "dense")],
            [ChildSearchHit(rewritten, 1, 0.9, "semantic", "sparse")],
            [ChildSearchHit(original, 2, 0.7, "semantic", "sparse")],
        ],
        {"original": 1.0, "semantic": 0.5},
    )

    assert [hit.child.child_id for hit in result] == ["child-original", "child-rewritten"]
    assert len(result[0].evidence) == 2


def test_parent_expansion_and_reranking_return_distinct_top_parents() -> None:
    parent_store = InMemoryParentStore()
    parent_store.upsert(
        [
            ParentChunk("parent-1", "doc-1", 0, "first", 1),
            ParentChunk("parent-2", "doc-1", 1, "second", 1),
        ]
    )
    children = weighted_rrf(
        [
            [
                ChildSearchHit(_child("child-1", "parent-1"), 1, 0.9, "original", "dense"),
                ChildSearchHit(_child("child-2", "parent-2"), 2, 0.8, "original", "dense"),
            ]
        ],
        {"original": 1.0},
    )
    candidates = expand_parents(children, parent_store)

    class ReverseReranker:
        def rerank(self, query: str, documents: list[str]) -> list[float]:
            return [0.1, 0.9]

    reranked = rerank_parents("query", candidates, ReverseReranker())

    assert [candidate.parent.parent_id for candidate in reranked] == ["parent-2", "parent-1"]
