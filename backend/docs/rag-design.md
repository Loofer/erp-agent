# Engineering RAG Design

## 1. Scope

The RAG module provides reusable document ingestion and retrieval for the ERP
agent and future features. It supports parent-child splitting, semantic
splitting, dense plus sparse retrieval, weighted Reciprocal Rank Fusion (RRF),
reranking, and request-scoped prompt context.

The initial source root is `backend/doc/`. Supported inputs are Markdown, text,
PDF, and DOCX. `llm-wiki-web/scripts/compile.py` is a reference for format
normalization, source metadata, and hash-based incremental processing. Its wiki
generation step is not part of the online retrieval path.

## 2. Runtime flow

```text
HTTP request
  -> JWT middleware (temporary decoder) -> user_id, user_name
  -> ChatService.stream()
  -> QueryRewriter: original + semantic + keyword + intent queries
  -> HybridRetriever for every query
       dense ANN search in Milvus
       sparse BM25 search in Milvus
  -> weighted RRF and child de-duplication
  -> parent expansion and access filtering
  -> Cross-Encoder rerank
  -> top 3 parent documents
  -> graph.astream(context=RuntimeContext)
  -> dynamic prompt middleware -> build_system_prompt(context)
```

Retrieval is completed before the first graph token is streamed. Retrieval
failure must be observable and degradable: if the knowledge index is
unavailable, the agent continues without RAG context and states that the
knowledge source was unavailable when relevant.

## 3. Reusable module boundaries

All splitting and embedding logic belongs in `src/agent/rag/`, independent of
FastAPI, Deep Agents, or a particular document source:

```text
agent/rag/
  models.py          # Document, ParentChunk, ChildChunk, RetrievalHit
  parsers.py         # Parser protocol and PDF/DOCX/MD implementations
  normalize.py       # canonical text, title/path and source metadata
  splitter.py        # structural + semantic parent/child splitting
  embeddings.py      # EmbeddingProvider protocol and batch implementation
  milvus_store.py    # collection schema, upsert, delete, dense/sparse search
  retriever.py       # query fan-out, RRF, parent expansion, filters
  reranker.py        # RerankerProvider protocol and top-N rerank
  ingest.py          # directory scan, hash/version checks, indexing workflow
  prompts.py         # rewrite prompt and retrieval-context rendering
```

`EmbeddingProvider` and `RerankerProvider` must be protocols. The production
implementations are injected through settings, while tests use deterministic
fake providers. Embeddings are always batch-generated and cached by
`sha256(text + model + dimension)`.

## 4. Chunking contract

The parser first emits a normalized `ParsedDocument` with stable source and
location metadata. The splitter then:

1. Uses headings, lists, tables, and code fences as structural boundaries.
2. Groups adjacent sections into semantic parents, bounded by token count.
3. Splits each parent into smaller semantic children with overlap.
4. Assigns stable IDs derived from document hash, parent ordinal, and child
   ordinal; random UUIDs are not suitable for idempotent re-indexing.

Initial defaults are parent `800-1200` tokens, child `180-300` tokens, and
overlap `10-15%`. These are configuration values, not constants in the
splitter. Token counting must use the configured model tokenizer or an explicit
fallback documented in metrics.

Each child stores `parent_id`; each parent stores the full text and provenance.
Search indexes children, while prompt context uses the parent text plus the
best matching child excerpts as anchors.

## 5. Milvus data model

Milvus/Zilliz is the production retrieval backend. Use one collection per
knowledge domain or tenant policy, configurable with `MILVUS_COLLECTION`.

Required fields:

| Field | Purpose |
|---|---|
| `chunk_id` | Stable child primary key |
| `document_id` | Source document identity |
| `parent_id` | Parent expansion key |
| `content` | Child text for sparse search and rerank |
| `parent_content` | Parent text for prompt assembly, or a parent-store key |
| `dense_vector` | Embedding vector |
| `sparse_vector` | BM25/sparse representation |
| `metadata` | JSON metadata: title, path, page, section, hash, version, ACL |
| `is_active` | Soft-delete/version filtering |

### Parent storage policy

The production target is to keep complete parent content outside the vector
index:

```text
Milvus: child content + dense/sparse vectors + parent_id + small metadata
ParentStore: parent content, provenance, and document version
Redis: optional cache in front of ParentStore
```

Parent chunks are not independently vector-searched. Children are the retrieval
unit; after RRF and child de-duplication, the service expands `parent_id` via
`ParentStore`, then reranks the distinct parents and injects the top three.

SQLite is suitable for local development, PostgreSQL is suitable when parent
metadata and versioning need transactions, and S3/OSS is suitable for large or
long-lived document bodies. Redis should be treated as a cache, not the only
durable copy.

The current first-phase adapter duplicates `parent_content` in each Milvus row
so parent expansion works without a second backend. This is a temporary
compatibility implementation, not the final production storage policy. Before
production scale-up, complete this migration:

1. Add a durable `ParentStore` implementation and store one record per
   `parent_id` with document version and provenance metadata.
2. Remove `parent_content` from the Milvus schema and retain only `parent_id`.
3. Update ingestion to upsert parents to `ParentStore` and children to Milvus
   in one idempotent document-version workflow.
4. Update retrieval expansion to batch-load parents by `parent_id`, with an
   optional Redis cache and bounded fallback behavior.
5. Reindex a validation collection and compare Recall@K, rerank quality,
   prompt size, latency, and storage consumption before switching the active
   collection.

Do not delete the existing collection as part of this migration. Use a new
versioned collection name, validate it, then switch `MILVUS_COLLECTION`.

The exact sparse-field/index syntax depends on the deployed `pymilvus` and
Milvus versions. It must be validated against the target server before coding;
do not silently substitute an application-side BM25 implementation in
production. If parent text makes rows too large, store it in PostgreSQL and
keep `parent_id` plus a cacheable lookup key in Milvus.

## 6. Query rewriting and retrieval

The rewrite LLM returns strict JSON with three fields:

```json
{
  "semantic": "同义词和自然表达",
  "keyword": "型号、零件号、状态等精确词",
  "intent": "保留约束条件的完整业务问法"
}
```

The original query is always retained. Each of the four queries runs through
dense and sparse search. Candidate identity is `chunk_id`; duplicate hits are
merged before parent expansion.

Use weighted RRF so the original query has the highest weight initially. Keep
per-hit diagnostics (`query_type`, `channel`, rank, raw score, fused score) for
evaluation and tracing. Suggested starting values: per-channel `top_k=20`, RRF
`k=60`, fused child candidates `30`, parent candidates `12`, rerank output `3`.

Reranking operates on the query and parent candidates, not on independently
returned duplicate children. Apply ACL/tenant filters before reranking and
before prompt construction.

## 7. Prompt and request context

The graph is created once at application startup, so request-specific documents
must not be concatenated into a global immutable prompt. Add a custom Deep
Agents middleware after the built-in stack. It reads the invocation context and
constructs:

```text
build_system_prompt(
  user_id=..., user_name=..., current_time=..., retrieval_context=...
)
```

The prompt must delimit retrieved text, include source IDs, forbid treating
retrieved text as instructions, and require an explicit uncertainty statement
when the answer is not supported by the context.

`user_id`, `user_name`, and `current_time` are request-scoped values. They must
not be persisted inside the shared graph object or used to build a global
singleton prompt.

## 8. JWT middleware (temporary)

Add a FastAPI HTTP middleware that reads `Authorization: Bearer <token>` and
decodes claims without signature verification in local development only. It
maps `sub` to `user_id` and `name`/`preferred_username` to `user_name`, then
stores a typed `RequestUser` on `request.state`.

The chat request model should stop accepting an authoritative user identity
from the client. The router passes `request.state.user` to `ChatService`; the
service still writes `user_id` and `agent_id` into checkpoint config and passes
`user_id`, `user_name`, and `agent_id` in graph context. Production must replace
the decoder with issuer, audience, expiry, and signature validation.

## 9. Configuration

Use `load_settings()` for all RAG settings. Required groups are Milvus URI/token
and collection, embedding model/dimension, splitter limits, reranker model,
rewrite model, candidate limits, RRF constant, and an ingestion source root
defaulting to `backend/doc/`. Never read these values directly from
`os.environ` in feature code.

## 10. Observability and evaluation

Emit one retrieval trace per request containing rewrite output, candidate
counts, fused/reranked IDs, latency by stage, model versions, and whether the
result was empty or degraded. Do not log raw user documents by default.

Create an offline evaluation set with query, relevant document IDs, and expected
answer evidence. Track Recall@K, MRR/nDCG before rerank, nDCG after rerank,
answer faithfulness, empty-result rate, and p50/p95 latency.

## 11. Implementation order

1. Define models and parser registry; add `backend/doc/` scan and hash state.
2. Replace the current prototype splitter with batched, configurable semantic
   parent/child splitting.
3. Implement Milvus collection setup, upsert/delete, and dense/sparse search.
4. Add query rewriting, weighted RRF, parent expansion, ACL filtering, and
   reranker interfaces.
5. Add JWT request context and dynamic prompt middleware.
6. Integrate `ChatService.stream()` and add unit, integration, and offline
   retrieval tests.

The current ingestion entry point is `python scripts/ingest_rag.py` from the
`backend/` directory. It creates the configured collection, skips unchanged
source checksums, and writes `.rag-state.json` beneath the source root.

## 12. Confirmed deployment decisions

- **Vector database:** Zilliz Cloud Serverless free tier. Configure
  `ZILLIZ_URI`, `ZILLIZ_TOKEN`, and `MILVUS_COLLECTION`; never depend on a local
  Milvus process in the application runtime.
- **Client:** `pymilvus==2.6.17` is pinned after verifying the installed client
  API. The native BM25 Function API and sparse index still require a smoke test
  against the target Zilliz collection before ingestion is enabled.
- **Identity:** the temporary JWT decoder maps `sub` to `user_id` and the
  `username` claim to `user_name`. Documents have no ACL filter in the first
  release.
- **Reranker:** use a local Cross-Encoder by default. For this Chinese ERP
  workload, `BAAI/bge-reranker-v2-m3` is the general multilingual choice;
  `maidalun1020/bce-reranker-base_v1` is a smaller Chinese-focused alternative.
  Run it through `sentence-transformers`/`FlagEmbedding` and batch the 12
  parent candidates. Keep an OpenAI-compatible reranker adapter as an optional
  fallback, not the default, to avoid per-query cost, network latency, and
  sending internal document text to a third party.
  Install the optional runtime with `uv sync --extra rag-rerank`; when it is
  absent, retrieval remains available but uses the fused parent order.

## 13. Deep Agents architecture decisions

- **Fit:** keep Deep Agents for the long-running, checkpointed ERP workflow;
  RAG itself remains a regular service pipeline because retrieval is a bounded
  request-time operation and does not need planning or delegation.
- **Backend:** keep the existing `CompositeBackend`: ephemeral state for the
  run, PostgreSQL-backed `StoreBackend` for durable user memory, and read-only
  filesystem routes for bundled guidance and skills. Milvus is the RAG index,
  not a Deep Agents filesystem backend.
- **Subagents:** no RAG subagent. Query rewriting, retrieval, fusion, and
  reranking are deterministic/application services whose combined result is
  injected into the parent agent.
- **Human-in-the-loop:** no approval gate for read-only retrieval. Existing
  ERP mutations retain their current native HITL rules.
- **Middleware:** add one custom request-context prompt middleware after the
  built-in Deep Agents stack. It transforms the model request to append the
  current user, time, and retrieved context; no retrieval tool is exposed to
  the model for this prefetch path.
- **Context limits:** preserve built-in summarization behavior. Retrieved
  parents are capped at three and each source is truncated by a configured
  character/token budget; large source files stay in Milvus and are never
  copied wholesale into the prompt.
- **Checkpointing:** continue using the existing PostgreSQL
  `AsyncPostgresSaver`. Retrieval diagnostics may be attached to run metadata,
  but the full document text must not be duplicated into checkpoint metadata.
