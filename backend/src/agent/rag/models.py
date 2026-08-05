"""Framework-independent RAG document and retrieval data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedDocument:
    """Canonical document emitted by a source parser."""

    document_id: str
    source_path: str
    title: str
    content: str
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParentChunk:
    """A context-sized section used to assemble the final prompt."""

    parent_id: str
    document_id: str
    ordinal: int
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChildChunk:
    """A retrieval-sized portion of a parent section."""

    child_id: str
    document_id: str
    parent_id: str
    ordinal: int
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SplitResult:
    """The parent and child records created from one document version."""

    parents: tuple[ParentChunk, ...]
    children: tuple[ChildChunk, ...]
