# Backend Architecture

This document describes the backend that is currently implemented in `backend/`.
It is intentionally explicit about optional services and development-only
boundaries so that the architecture does not imply capabilities that are still
planned.

## 1. Runtime Shape

The backend is a FastAPI application around one Deep Agents/LangGraph graph.
The process owns the HTTP transport, graph construction, ERP tool clients, and
the PostgreSQL resources shared by all requests.

```text
Vue client
   |
   |  Bearer JWT (development claim decoder)
   v
FastAPI /api
   |-- JwtIdentityMiddleware  -> request user
   |-- chat router             -> SSE endpoints and history
   `-- ChatService.stream()
          |-- optional RAG retrieval
          |-- request context (user, time, retrieved documents)
          `-- LangGraph/Deep Agents graph
                 |-- primary erp-agent
                 |     |-- knowledge/RAG tools
                 |     |-- Skills and filesystem backend
                 |     |-- safety middleware
                 |     `-- task -> declarative subagent
                 |             |-- supplier_manager
                 |             |-- procurement_order
                 |             `-- procurement_analyst
                 `-- PostgreSQL checkpoint + durable memory
```

`src/api_view/web_main.py` composes the application and uses a lifespan to
create the PostgreSQL store, asynchronous checkpointer, conversation repository,
optional retriever, and graph before serving requests. A RAG initialisation
failure is logged and leaves chat available without retrieval.

## 2. Request Lifecycle

1. `JwtIdentityMiddleware` processes `/api/*` requests and places `sub` and
   `username` on the request. The decoder currently accepts unsigned JWTs and
   does not verify issuer, audience, expiry, or signature; this is a development
   boundary, not production authentication.
2. `POST /api/chat/stream` creates a UUIDv7 thread ID when needed. The resume
   endpoint sends a LangGraph `Command(resume=...)` for the existing thread.
3. `ChatService` builds checkpoint metadata (`user_id`, `agent_id`, timestamps)
   and runtime context. For a new message it invokes the optional `HybridRetriever`
   in a worker thread and renders selected parents as delimited, untrusted
   reference content.
4. The graph is streamed with LangGraph v2 events and `subgraphs=True`.
   `ChatService` projects these into the stable SSE contract: `conversation`,
   `message_chunk`, `tool_call_start`, `tool_call_end`, `agent_routing`,
   `interrupt`, `complete`, and `error`.
5. LangGraph checkpoints retain the complete message state and pending
   interrupts. `/api/history` reads thread metadata from checkpoint rows, and
   `/api/chat/{thread_id}/messages` projects the checkpoint state into the
   user-visible timeline. There is no second event-log table.

## 3. Agent Construction

`src/agent/main_agent.py` is the composition root. `load_agent_graph()` loads
the model and YAML definitions, builds the optional RAG retriever, creates the
ERP `ApiClient`, and calls `deepagents.create_deep_agent()`.

The primary `erp-agent` receives only parent-level knowledge tools. Domain and
mutation tools are registered in `src/agent/tools/` but are handed to
subagents through validated YAML files in `src/agent/subagents/configs/`:

| Subagent | Responsibility | Protected writes |
| --- | --- | --- |
| `supplier_manager` | supplier search and supplier workflow | `create_supplier` |
| `procurement_order` | order fields and order mutations | `create_order`, `update_order` |
| `procurement_analyst` | ERP aggregation, analysis, and chart/report output | none |

`loader.py` validates names, prompts, tool references, skills, backend type, and
`interrupt_on` decisions before constructing `SubAgent` values. A write tool is
therefore paused by Deep Agents before the HTTP request; prompts alone are not
the approval mechanism. The only configured execution backend is
`local_shell`, used by the procurement analyst and subject to the documented
filesystem/resource limitations.

## 4. Context, Middleware, and Safety

The graph receives a typed `MemoryContext` containing the user, agent, current
time, and retrieval context. `RequestContextPromptMiddleware` rebuilds the
request system prompt from that context on every model call.

The registered middleware stack currently includes:

- `PromptInjectionMiddleware`: detects common instruction-injection patterns
  and can terminate the run before a model call; it also provides a tool-call
  fallback check.
- `RequestContextPromptMiddleware`: injects identity, time, and explicitly
  untrusted RAG material.
- Tool-call limits: bounds calls per thread and per run to contain loops and
  accidental token/resource consumption.
- PII middleware: redacts, masks, or blocks email, phone, ID-card, credit-card,
  and API-key patterns according to each configured policy.

Retrieved text is evidence, not an instruction. Current inventory, prices,
orders, and other live ERP facts must come from registered ERP tools; RAG is for
document knowledge and workflow guidance.

## 5. Filesystem and Memory Backends

`src/agent/memory/runtime.py` exposes a `CompositeBackend`:

| Virtual path | Backend | Intended use |
| --- | --- | --- |
| `/memory/` | read-only `FilesystemBackend` | bundled global guidance |
| `/skills/` | read-only `FilesystemBackend` | versioned progressive-disclosure Skills |
| `/memories/` | PostgreSQL `StoreBackend` | user long-term preferences and notes |
| `/sandbox/` | `LocalShellBackend` | temporary local execution workspace |

`/memories/` is namespaced as `(agent_id, user_id, "memories")`; invalid
namespace components are rejected. `FilesystemPermission` denies writes to
shared memory and Skills while allowing reads and permits user-memory reads and
writes. Because no global deny rule is configured, unmatched virtual paths use
the Deep Agents default and must be reviewed when adding routes.

Automatic conversation summarisation and evicted-history files are Deep Agents
runtime behavior. They are distinct from durable user memory and from the
PostgreSQL checkpoint state.

## 6. Optional Hybrid RAG

When Zilliz/Milvus settings are configured, `agent.rag.runtime` builds an
`HybridRetriever` with OpenAI-compatible embeddings, a Milvus child-chunk store,
JSON query rewriting, and an optional FlagEmbedding reranker.

```text
original query
   + semantic / keyword / intent rewrites
       -> dense + BM25 per variant
           -> weighted RRF
               -> child-to-parent expansion
                   -> optional rerank
                       -> top parent documents in request context
```

The original query has the highest fusion weight (`1.0`); keyword, intent, and
semantic variants use `0.9`, `0.85`, and `0.8`. Empty or failed rewriting falls
back to the original query. Retrieved parents retain `source_id` metadata and
are rendered as `<retrieved_document>` blocks. Ingestion and collection setup
are separate from request serving (`agent/rag/ingest.py` and `milvus_store.py`).

## 7. Structured Visualization

Chart output is a protocol, not an arbitrary model-generated frontend config.
`src/visualization/schema.py` validates the v1 chart document and
`renderer_contract.py` converts the validated specification to a browser-safe
ECharts payload. Supported chart types are `bar`, `line`, `pie`, `table`, and
`kpi`; unsupported fields and oversized documents fail validation. The
procurement-analysis Skill defines when to emit one-line NDJSON chart data and
when to write a longer report to `/analysis/`.

## 8. Evaluation and Operations

`backend/evals/` runs the production graph with a read-only ERP mock transport,
records retrieval and tool traces, and optionally evaluates RAGAS metrics plus
deterministic tool correctness. It is an offline regression harness, not a
production monitoring service.

The current operational foundations are PostgreSQL checkpoint/store state,
structured logging, SSE metadata, and `/health`. Signature-verified
authentication, distributed tracing/metrics, remote sandbox provisioning,
rate/cost limiting, and deployment orchestration remain follow-up work rather
than implemented backend components.

## Related Design Notes

- [Memory and conversation design](docs/memory/Memory-Practical.md)
- [Filesystem permissions](docs/memory/Filesystem-Permission-Practical.md)
- [Sandbox boundaries](docs/memory/Sandbox-Practical.md)
- [HITL approval](docs/hitl/HITL-Approval-Practical.md)
- [RAG query rewriting](docs/rag/Query-Rewrite-Practical.md)
- [RAG middleware defence](docs/middleware/RAG-Agent-Middleware-Defense-and-Context.md)
- [Chart output contract](docs/chart-render/Chart-Output-Practical.md)
- [Skill architecture](docs/skills/Skill-Architecture-Practical.md)
- [RAGAS evaluation](docs/evals/Ragas-Agent-Evaluation-Practical.md)
