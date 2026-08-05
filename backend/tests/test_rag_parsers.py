from pathlib import Path

import pytest

from agent.rag.parsers import ParserRegistry


def test_markdown_parser_preserves_title_and_checksum(tmp_path: Path) -> None:
    source = tmp_path / "catalog.md"
    source.write_text("# Brake Catalog\n\nPads and discs.", encoding="utf-8")

    document = ParserRegistry().parse(source)

    assert document.title == "Brake Catalog"
    assert document.content == "# Brake Catalog\n\nPads and discs."
    assert len(document.checksum) == 64


def test_unsupported_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "catalog.xlsx"
    source.write_text("not used", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported knowledge source"):
        ParserRegistry().parse(source)
