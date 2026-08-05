"""Zilliz Cloud implementation of RAG indexing and hybrid child search."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pymilvus import DataType, Function, FunctionType, MilvusClient

from .embeddings import EmbeddingProvider
from .models import ChildChunk, ParentChunk

_OUTPUT_FIELDS = [
    "child_id",
    "document_id",
    "parent_id",
    "parent_ordinal",
    "parent_content",
    "content",
    "child_ordinal",
    "metadata",
]


class MilvusChunkStore:
    """Stores child vectors and duplicate parent context in one collection.

    The BM25 function is maintained server-side by Zilliz. Parent text is
    intentionally duplicated per child so a vector hit expands without another
    backend round trip; parent/child limits keep this bounded.
    """

    def __init__(
            self,
            *,
            uri: str,
            token: str,
            collection_name: str,
            embedding_provider: EmbeddingProvider,
            embedding_dimension: int,
            client: MilvusClient | None = None,
    ) -> None:
        if not uri or not token:
            raise ValueError("Zilliz URI and token are required for the Milvus store.")
        self._client = client or MilvusClient(uri=uri, token=token)
        self._collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._embedding_dimension = embedding_dimension

    def ensure_collection(self) -> None:
        """Create the child collection and dense/BM25 indexes when absent."""
        if self._client.has_collection(self._collection_name):
            return
        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("child_id", DataType.VARCHAR, is_primary=True, max_length=160)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("parent_id", DataType.VARCHAR, max_length=160)
        schema.add_field("parent_ordinal", DataType.INT64)
        schema.add_field("parent_content", DataType.VARCHAR, max_length=65_535)
        schema.add_field("content", DataType.VARCHAR, max_length=65_535, enable_analyzer=True)
        schema.add_field("child_ordinal", DataType.INT64)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=self._embedding_dimension)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="content_bm25",
                function_type=FunctionType.BM25,
                input_field_names=["content"],
                output_field_names=["sparse_vector"],
            )
        )
        indexes = self._client.prepare_index_params()
        indexes.add_index("dense_vector", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index("sparse_vector", index_type="AUTOINDEX", metric_type="BM25")
        self._client.create_collection(
            self._collection_name, schema=schema, index_params=indexes
        )

    def upsert(self, parents: list[ParentChunk], children: list[ChildChunk]) -> None:
        """Embed child text in batches and upsert it with its parent context."""
        if not children:
            return
        parents_by_id = {parent.parent_id: parent for parent in parents}
        vectors = self._embedding_provider.embed_documents([child.content for child in children])
        if len(vectors) != len(children):
            raise ValueError("Embedding provider returned an unexpected vector count.")
        rows = []
        for child, vector in zip(children, vectors, strict=True):
            if len(vector) != self._embedding_dimension:
                raise ValueError("Embedding vector dimension does not match Milvus schema.")
            parent = parents_by_id.get(child.parent_id)
            if parent is None:
                raise ValueError(f"Missing parent for child {child.child_id}.")
            rows.append(
                {
                    "child_id": child.child_id,
                    "document_id": child.document_id,
                    "parent_id": child.parent_id,
                    "parent_ordinal": parent.ordinal,
                    "parent_content": parent.content,
                    "content": child.content,
                    "child_ordinal": child.ordinal,
                    "metadata": child.metadata,
                    "dense_vector": vector,
                }
            )
        self._client.upsert(self._collection_name, rows)

    def search_dense(self, query: str, limit: int) -> list[tuple[ChildChunk, float]]:
        vector = self._embedding_provider.embed_query(query)
        if len(vector) != self._embedding_dimension:
            raise ValueError("Query vector dimension does not match Milvus schema.")
        result = self._client.search(
            self._collection_name,
            data=[vector],
            anns_field="dense_vector",
            limit=limit,
            output_fields=_OUTPUT_FIELDS,
        )
        return _search_results(result)

    def search_sparse(self, query: str, limit: int) -> list[tuple[ChildChunk, float]]:
        result = self._client.search(
            self._collection_name,
            data=[query],
            anns_field="sparse_vector",
            limit=limit,
            output_fields=_OUTPUT_FIELDS,
        )
        return _search_results(result)

    def get_many(self, parent_ids: list[str]) -> list[ParentChunk]:
        if not parent_ids:
            return []
        expression = f"parent_id in {json.dumps(parent_ids, ensure_ascii=False)}"
        rows = self._client.query(
            self._collection_name,
            filter=expression,
            output_fields=_OUTPUT_FIELDS,
        )
        by_parent: dict[str, ParentChunk] = {}
        for row in rows:
            parent_id = str(row["parent_id"])
            by_parent.setdefault(
                parent_id,
                ParentChunk(
                    parent_id=parent_id,
                    document_id=str(row["document_id"]),
                    ordinal=int(row["parent_ordinal"]),
                    content=str(row["parent_content"]),
                    token_count=0,
                    metadata=_metadata(row.get("metadata")),
                ),
            )
        return [by_parent[parent_id] for parent_id in parent_ids if parent_id in by_parent]


def _search_results(result: Sequence[Sequence[dict[str, Any]]]) -> list[tuple[ChildChunk, float]]:
    if not result:
        return []
    return [
        (_child_from_row(hit.get("entity", hit)), float(hit.get("distance", 0.0)))
        for hit in result[0]
    ]


def _child_from_row(row: dict[str, Any]) -> ChildChunk:
    return ChildChunk(
        child_id=str(row["child_id"]),
        document_id=str(row["document_id"]),
        parent_id=str(row["parent_id"]),
        ordinal=int(row["child_ordinal"]),
        content=str(row["content"]),
        token_count=0,
        metadata=_metadata(row.get("metadata")),
    )


def _metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
