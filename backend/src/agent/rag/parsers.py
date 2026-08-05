"""Source-file parsers for the RAG ingestion pipeline."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree

from .models import ParsedDocument


class DocumentParser(Protocol):
    """Parses one or more source file extensions into canonical text."""

    extensions: tuple[str, ...]

    def parse(self, path: Path) -> ParsedDocument: ...


class ParserRegistry:
    """Routes source files to parsers without coupling ingestion to formats."""

    def __init__(self, parsers: tuple[DocumentParser, ...] | None = None) -> None:
        active_parsers = parsers or (TextParser(), DocxParser(), PdfParser())
        self._parsers = {
            extension: parser
            for parser in active_parsers
            for extension in parser.extensions
        }

    def parse(self, path: Path) -> ParsedDocument:
        parser = self._parsers.get(path.suffix.lower())
        if parser is None:
            raise ValueError(f"Unsupported knowledge source: {path.name}")
        return parser.parse(path)


class TextParser:
    """Parser for plain text and Markdown sources."""

    extensions = (".md", ".markdown", ".txt")

    def parse(self, path: Path) -> ParsedDocument:
        content = path.read_text(encoding="utf-8-sig").strip()
        return _parsed_document(path, content, _markdown_title(content, path.stem))


class DocxParser:
    """Minimal DOCX parser using the standard-library OOXML reader."""

    extensions = (".docx",)

    def parse(self, path: Path) -> ParsedDocument:
        try:
            with zipfile.ZipFile(path) as archive:
                document_xml = archive.read("word/document.xml")
        except (KeyError, zipfile.BadZipFile) as exc:
            raise ValueError(f"Invalid DOCX source: {path.name}") from exc

        root = ElementTree.fromstring(document_xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = []
        for paragraph in root.iter(f"{namespace}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            if text.strip():
                paragraphs.append(text.strip())
        content = "\n\n".join(paragraphs)
        return _parsed_document(path, content, path.stem)


class PdfParser:
    """PDF parser with a deliberately optional dependency."""

    extensions = (".pdf",)

    def parse(self, path: Path) -> ParsedDocument:
        try:
            # TODO Replace    pymupdf4llm
            # PDF
            # 提取引擎（按优先级自动选择，也可手动指定）：
            # pymupdf4llm  — 最佳质量，保留表格 / 公式结构（推荐）
            # markitdown   — 微软出品，通用性强
            # pdfminer     — 纯文本提取，无额外依赖风险
            # pypdf        — 轻量级备选
            # OCR方案 Docling、MinerU、Marker‑pdf、Unstructured
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires the optional pypdf package.") from exc

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        content = "\n\n".join(page.strip() for page in pages if page.strip())
        return _parsed_document(path, content, path.stem, {"page_count": len(pages)})


def _parsed_document(
    path: Path,
    content: str,
    title: str,
    metadata: dict[str, object] | None = None,
) -> ParsedDocument:
    if not content:
        raise ValueError(f"Knowledge source is empty: {path.name}")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    document_id = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24]
    return ParsedDocument(
        document_id=document_id,
        source_path=str(path),
        title=title,
        content=content,
        checksum=checksum,
        metadata=dict(metadata or {}),
    )


def _markdown_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", content, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback
