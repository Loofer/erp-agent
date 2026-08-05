"""Strict query-rewrite contracts for hybrid RAG retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class QueryVariants:
    """Original query plus three intentionally different retrieval views."""

    original: str
    semantic: str
    keyword: str
    intent: str

    def items(self) -> list[tuple[str, str]]:
        seen: set[str] = set()
        result: list[tuple[str, str]] = []
        for kind, query in (("original", self.original), ("semantic", self.semantic),
                            ("keyword", self.keyword), ("intent", self.intent)):
            normalized = query.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append((kind, normalized))
        return result


class QueryRewriter(Protocol):
    def rewrite(self, query: str) -> QueryVariants: ...


class JsonQueryRewriter:
    """Uses a chat model that returns JSON or degrades to the original query."""

    _SYSTEM_PROMPT = """Return only JSON with semantic, keyword, and intent fields.
semantic expands business synonyms and fixes phrasing. keyword preserves exact
model numbers, part numbers, states, and filter fields. intent preserves the
user's full business objective and constraints. Do not answer the question."""

    def __init__(self, model: object) -> None:
        self._model = model

    def rewrite(self, query: str) -> QueryVariants:
        try:
            response = self._model.invoke([
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ])
            content = getattr(response, "content", response)
            parsed = json.loads(content if isinstance(content, str) else "")
            if not isinstance(parsed, dict):
                raise TypeError("Query rewrite response was not an object.")
            return QueryVariants(
                query,
                _string_value(parsed, "semantic", query),
                _string_value(parsed, "keyword", query),
                _string_value(parsed, "intent", query),
            )
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            return QueryVariants(query, query, query, query)


def _string_value(payload: dict[str, object], field: str, fallback: str) -> str:
    value = payload.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else fallback
