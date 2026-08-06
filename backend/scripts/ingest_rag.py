"""Incrementally ingest backend/doc sources into the configured Zilliz collection."""

import argparse
from pathlib import Path

from langchain_openai import OpenAIEmbeddings

from backend.configs.settings import load_settings
from agent.rag.ingest import DirectoryIngestor
from agent.rag.milvus_store import MilvusChunkStore
from agent.rag.parsers import ParserRegistry
from agent.rag.providers import HashEmbeddingProvider, OpenAIEmbeddingProvider
from agent.rag.splitter import SemanticParentChildSplitter, SplitterConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline-embedding",
        action="store_true",
        help="Use deterministic embeddings for pipeline tests; never use in production.",
    )
    args = parser.parse_args()
    settings = load_settings()
    if not settings.zilliz_uri or not settings.zilliz_token:
        raise SystemExit("ZILLIZ_URI and ZILLIZ_TOKEN must be configured.")

    if args.offline_embedding:
        embedding = HashEmbeddingProvider(settings.embed_dim)
    else:
        embedding = OpenAIEmbeddingProvider(
            OpenAIEmbeddings(
                model=settings.embed_model,
                dimensions=settings.embed_dim,
                api_key=settings.api_key,
                base_url=settings.base_url or None,
            )
        )
    store = MilvusChunkStore(
        uri=settings.zilliz_uri,
        token=settings.zilliz_token.get_secret_value(),
        collection_name=settings.milvus_collection,
        embedding_provider=embedding,
        embedding_dimension=settings.embed_dim,
    )
    store.ensure_collection()
    splitter = SemanticParentChildSplitter(
        embedding_provider=embedding,
        config=SplitterConfig(
            parent_max_tokens=settings.parent_chunk_size,
            parent_overlap_tokens=settings.parent_overlap,
            child_max_tokens=settings.child_chunk_size,
            child_overlap_tokens=settings.child_overlap,
            semantic_threshold=settings.semantic_threshold,
        ),
    )
    source_root = Path(settings.rag_source_root)
    report = DirectoryIngestor(
        source_root=source_root,
        parser_registry=ParserRegistry(),
        splitter=splitter,
        index=store,
        state_path=source_root / ".rag-state.json",
    ).run()
    print(
        f"indexed={len(report.indexed_files)} skipped={len(report.skipped_files)} "
        f"parents={report.parent_count} children={report.child_count}"
    )


if __name__ == "__main__":
    main()
