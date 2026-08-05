from agent.rag.models import ParsedDocument
from agent.rag.splitter import SemanticParentChildSplitter, SplitterConfig


def _document(content: str) -> ParsedDocument:
    return ParsedDocument(
        document_id="document-1",
        source_path="doc/catalog.md",
        title="Catalog",
        content=content,
        checksum="checksum",
    )


def test_splitter_creates_stable_parent_child_relationships() -> None:
    splitter = SemanticParentChildSplitter(
        config=SplitterConfig(
            parent_max_tokens=12,
            parent_overlap_tokens=2,
            child_max_tokens=6,
            child_overlap_tokens=1,
        )
    )
    document = _document("# Brakes\nPads stop the vehicle.\n\nDiscs dissipate heat.")

    first = splitter.split(document)
    second = splitter.split(document)

    assert first.parents == second.parents
    assert first.children == second.children
    assert len(first.parents) >= 1
    assert len(first.children) >= len(first.parents)
    assert {child.parent_id for child in first.children} <= {
        parent.parent_id for parent in first.parents
    }


class FixedEmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "brake" in text.lower() else [0.0, 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


def test_semantic_boundary_splits_dissimilar_units() -> None:
    splitter = SemanticParentChildSplitter(
        embedding_provider=FixedEmbeddingProvider(),
        config=SplitterConfig(parent_max_tokens=100, semantic_threshold=0.8),
    )

    result = splitter.split(_document("Brake pads fit cars.\n\nInventory prices change."))

    assert len(result.parents) == 2
