"""Parent storage contract used by retrieval implementations."""

from __future__ import annotations

from typing import Protocol

from .models import ParentChunk


class ParentStore(Protocol):
    """Loads expanded parent context after child retrieval."""

    def get_many(self, parent_ids: list[str]) -> list[ParentChunk]: ...

    def upsert(self, parents: list[ParentChunk]) -> None: ...


class InMemoryParentStore:
    """Deterministic parent store for unit tests and local development."""

    def __init__(self) -> None:
        self._parents: dict[str, ParentChunk] = {}

    def get_many(self, parent_ids: list[str]) -> list[ParentChunk]:
        return [self._parents[parent_id] for parent_id in parent_ids if parent_id in self._parents]

    def upsert(self, parents: list[ParentChunk]) -> None:
        self._parents.update({parent.parent_id: parent for parent in parents})
