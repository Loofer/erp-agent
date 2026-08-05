"""Incremental ingestion orchestration for the configured document directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import ChildChunk, ParentChunk
from .parsers import ParserRegistry
from .splitter import SemanticParentChildSplitter


class ChunkIndex(Protocol):
    """Destination abstraction for parent and child chunks."""

    def upsert(self, parents: list[ParentChunk], children: list[ChildChunk]) -> None: ...


@dataclass(frozen=True)
class IngestReport:
    indexed_files: tuple[Path, ...]
    skipped_files: tuple[Path, ...]
    parent_count: int
    child_count: int


class DirectoryIngestor:
    """Indexes changed supported files and stores only compact source state."""

    def __init__(
        self,
        source_root: Path,
        parser_registry: ParserRegistry,
        splitter: SemanticParentChildSplitter,
        index: ChunkIndex,
        state_path: Path,
    ) -> None:
        self._source_root = source_root
        self._parser_registry = parser_registry
        self._splitter = splitter
        self._index = index
        self._state_path = state_path

    def run(self) -> IngestReport:
        state = self._load_state()
        indexed: list[Path] = []
        skipped: list[Path] = []
        parent_count = 0
        child_count = 0
        for path in sorted(item for item in self._source_root.rglob("*") if item.is_file()):
            if path.name == "README.md":
                continue
            try:
                document = self._parser_registry.parse(path)
            except ValueError:
                continue
            key = str(path.relative_to(self._source_root)).replace("\\", "/")
            if state.get(key) == document.checksum:
                skipped.append(path)
                continue
            result = self._splitter.split(document)
            self._index.upsert(list(result.parents), list(result.children))
            state[key] = document.checksum
            indexed.append(path)
            parent_count += len(result.parents)
            child_count += len(result.children)
        self._save_state(state)
        return IngestReport(
            indexed_files=tuple(indexed),
            skipped_files=tuple(skipped),
            parent_count=parent_count,
            child_count=child_count,
        )

    def _load_state(self) -> dict[str, str]:
        if not self._state_path.exists():
            return {}
        data = json.loads(self._state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _save_state(self, state: dict[str, str]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
