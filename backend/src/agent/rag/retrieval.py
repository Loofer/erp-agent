"""Query fusion, parent expansion, and reranking orchestration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from .models import ChildChunk, ParentChunk
from .rag_store import ParentStore


@dataclass(frozen=True)
class ChildSearchHit:
    """A ranked child result from one query and one retrieval channel."""

    child: ChildChunk
    rank: int
    raw_score: float
    query_type: str
    channel: str


@dataclass(frozen=True)
class FusedChildHit:
    """A de-duplicated child hit with its transparent RRF evidence."""

    child: ChildChunk
    score: float
    evidence: tuple[ChildSearchHit, ...]


@dataclass(frozen=True)
class ParentCandidate:
    """A parent selected through one or more matching children."""

    parent: ParentChunk
    score: float
    matching_children: tuple[FusedChildHit, ...]


class RerankerProvider(Protocol):
    """Scores parent passages for a query in one batch."""

    def rerank(self, query: str, documents: Sequence[str]) -> list[float]: ...


def weighted_rrf(
    rankings: Sequence[Sequence[ChildSearchHit]],
    weights: Mapping[str, float],
    *,
    constant: int = 60,
    limit: int = 30,
) -> list[FusedChildHit]:
    """Fuse ranked dense/sparse results while preserving source diagnostics."""
    by_child: dict[str, list[ChildSearchHit]] = defaultdict(list)
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for hit in ranking:
            weight = weights.get(hit.query_type, 1.0)
            scores[hit.child.child_id] += weight / (constant + hit.rank)
            by_child[hit.child.child_id].append(hit)

    fused = [
        FusedChildHit(
            child=hits[0].child,
            score=scores[child_id],
            evidence=tuple(sorted(hits, key=lambda hit: (hit.rank, hit.channel))),
        )
        for child_id, hits in by_child.items()
    ]
    return sorted(fused, key=lambda hit: (-hit.score, hit.child.child_id))[:limit]


def expand_parents(
    fused_children: Sequence[FusedChildHit],
    parent_store: ParentStore,
    *,
    limit: int = 12,
) -> list[ParentCandidate]:
    """Collapse child hits into distinct parent candidates for reranking."""
    by_parent: dict[str, list[FusedChildHit]] = defaultdict(list)
    for hit in fused_children:
        by_parent[hit.child.parent_id].append(hit)
    ordered_ids = sorted(
        by_parent,
        key=lambda parent_id: (-max(hit.score for hit in by_parent[parent_id]), parent_id),
    )[:limit]
    parents_by_id = {parent.parent_id: parent for parent in parent_store.get_many(ordered_ids)}
    return [
        ParentCandidate(
            parent=parents_by_id[parent_id],
            score=max(hit.score for hit in by_parent[parent_id]),
            matching_children=tuple(by_parent[parent_id]),
        )
        for parent_id in ordered_ids
        if parent_id in parents_by_id
    ]


def rerank_parents(
    query: str,
    candidates: Sequence[ParentCandidate],
    reranker: RerankerProvider | None,
    *,
    limit: int = 3,
) -> list[ParentCandidate]:
    """Return the highest-quality distinct parents for prompt context."""
    if reranker is None:
        return list(candidates[:limit])
    scores = reranker.rerank(query, [candidate.parent.content for candidate in candidates])
    if len(scores) != len(candidates):
        raise ValueError("Reranker returned a score count different from its candidates.")
    ordered = sorted(
        zip(candidates, scores, strict=True),
        key=lambda item: (-item[1], item[0].parent.parent_id),
    )
    return [candidate for candidate, _ in ordered[:limit]]
