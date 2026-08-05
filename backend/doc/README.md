# Knowledge Source Directory

This directory is the input root for the RAG ingestion pipeline.

Supported source files will include Markdown, plain text, PDF, DOCX, and other
formats handled by the document parser registry. Files are indexed into the
configured Milvus collection; this directory is not the runtime vector store.

## Layout

```text
backend/doc/
  README.md
  <knowledge files>.md
  <knowledge files>.pdf
  <knowledge files>.docx
```

The ingestion command should be idempotent. A source is reprocessed only when
its content hash, parser version, splitter version, embedding model, or index
schema version changes. Each indexed child must retain its `document_id`,
`parent_id`, source path, title/path metadata, and permission scope so retrieval
can expand a child hit back to its parent and enforce access filters.

Do not place secrets, temporary extraction output, or generated vector-store
files in this directory.
