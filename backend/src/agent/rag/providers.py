"""Production provider adapters with optional model dependencies."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from langchain_openai import OpenAIEmbeddings

from .embeddings import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Adapt LangChain OpenAI-compatible embeddings to the RAG protocol."""

    def __init__(self, embeddings: OpenAIEmbeddings) -> None:
        self._embeddings = embeddings

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline embedding for pipeline tests only."""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for index in range(max(0, len(text) - 2)):
            token = text[index : index + 3].lower().encode("utf-8")
            digest = hashlib.sha256(token).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimension
            vector[bucket] += 1.0 if digest[4] % 2 else -1.0
        magnitude = sum(value * value for value in vector) ** 0.5
        return [value / magnitude for value in vector] if magnitude else vector
