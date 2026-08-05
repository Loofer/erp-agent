"""Stable, reusable structural and semantic parent-child splitting."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from .embeddings import EmbeddingProvider, cosine_similarity
from .models import ChildChunk, ParentChunk, ParsedDocument, SplitResult

_HEADING = re.compile(r"^#{1,6}\s+.+$", flags=re.MULTILINE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?\u3002\uff01\uff1f])\s+|\n{2,}")
_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")


@dataclass(frozen=True)
class SplitterConfig:
    parent_max_tokens: int = 1_000
    parent_overlap_tokens: int = 120
    child_max_tokens: int = 240
    child_overlap_tokens: int = 32
    semantic_threshold: float = 0.72


class SemanticParentChildSplitter:
    """Split documents into stable parents and retrieval-sized children.

    Embeddings are optional. Without a provider the splitter still respects
    structural and token boundaries, which keeps ingestion testable offline.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        config: SplitterConfig | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._config = config or SplitterConfig()

    def split(self, document: ParsedDocument) -> SplitResult:
        units = _text_units(document.content)
        if not units:
            return SplitResult(parents=(), children=())
        embeddings = self._embed_units(units)
        parent_contents = self._build_parents(units, embeddings)
        parents: list[ParentChunk] = []
        children: list[ChildChunk] = []
        for parent_ordinal, content in enumerate(parent_contents):
            parent_id = _stable_id(document.document_id, "parent", parent_ordinal, content)
            parent = ParentChunk(
                parent_id=parent_id,
                document_id=document.document_id,
                ordinal=parent_ordinal,
                content=content,
                token_count=_token_count(content),
                metadata={"title": document.title, **document.metadata},
            )
            parents.append(parent)
            for child_ordinal, child_content in enumerate(self._build_children(content)):
                children.append(
                    ChildChunk(
                        child_id=_stable_id(
                            document.document_id,
                            "child",
                            parent_ordinal * 10_000 + child_ordinal,
                            child_content,
                        ),
                        document_id=document.document_id,
                        parent_id=parent_id,
                        ordinal=child_ordinal,
                        content=child_content,
                        token_count=_token_count(child_content),
                        metadata={"title": document.title, **document.metadata},
                    )
                )
        return SplitResult(parents=tuple(parents), children=tuple(children))

    def _embed_units(self, units: Sequence[str]) -> list[list[float]] | None:
        if self._embedding_provider is None:
            return None
        return self._embedding_provider.embed_documents(units)

    def _build_parents(
        self, units: Sequence[str], embeddings: list[list[float]] | None
    ) -> list[str]:
        groups: list[list[str]] = []
        current: list[str] = []
        for index, unit in enumerate(units):
            exceeds_limit = current and (
                _token_count("\n\n".join([*current, unit]))
                > self._config.parent_max_tokens
            )
            breaks_semantics = (
                current
                and embeddings is not None
                and cosine_similarity(embeddings[index - 1], embeddings[index])
                < self._config.semantic_threshold
            )
            if exceeds_limit or breaks_semantics:
                groups.append(current)
                current = _tail_within_budget(current, self._config.parent_overlap_tokens)
            current.append(unit)
        if current:
            groups.append(current)
        return ["\n\n".join(group) for group in groups]

    def _build_children(self, parent_content: str) -> list[str]:
        units = _text_units(parent_content)
        if not units:
            return []
        groups: list[list[str]] = []
        current: list[str] = []
        for unit in units:
            if current and _token_count("\n\n".join([*current, unit])) > self._config.child_max_tokens:
                groups.append(current)
                current = _tail_within_budget(current, self._config.child_overlap_tokens)
            current.append(unit)
        if current:
            groups.append(current)
        return ["\n\n".join(group) for group in groups]


def _text_units(content: str) -> list[str]:
    sections = _HEADING.split(content)
    headings = _HEADING.findall(content)
    units: list[str] = []
    for index, section in enumerate(sections):
        prefix = headings[index - 1] if index > 0 else ""
        fragments = [fragment.strip() for fragment in _SENTENCE_BOUNDARY.split(section) if fragment.strip()]
        if not fragments and prefix:
            fragments = [prefix]
        if prefix and fragments:
            fragments[0] = f"{prefix}\n{fragments[0]}"
        units.extend(fragments)
    return units


def _tail_within_budget(units: Sequence[str], budget: int) -> list[str]:
    tail: list[str] = []
    for unit in reversed(units):
        if tail and _token_count("\n\n".join([unit, *tail])) > budget:
            break
        tail.insert(0, unit)
    return tail


def _token_count(text: str) -> int:
    return len(_TOKEN.findall(text))


def _stable_id(document_id: str, kind: str, ordinal: int, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{document_id}:{kind}:{ordinal}:{digest}"
