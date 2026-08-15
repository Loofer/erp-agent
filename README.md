# Motorparts Agent

<p align="center">
  <strong>An AI agent harness for motor-parts Motorparts procurement workflows</strong><br />
  Reliable tool use, contextual retrieval, human approval, and resumable execution.
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> ·
  <a href="LICENSE">MIT License</a>
</p>

Motorparts Agent is an open-source engineering project that applies Harness
Engineering ideas to a concrete procurement domain. It combines a Deep Agents
runtime with LangGraph, Motorparts tools, specialised subagents, PostgreSQL-backed
state, hybrid RAG, safety middleware, and an evaluation runner.

The project is intentionally focused on the runtime around an LLM: how an agent
gets trustworthy context, uses bounded tools, pauses for human decisions, and
continues from durable state.

> **Project status:** actively evolving. Authentication, observability,
> deployment orchestration, and several advanced workflows remain in the
> roadmap.

## Architecture

![Motorparts Agent architecture](docs/images/motorparts-agent-architecture.png)

The architecture diagram separates the current runtime from planned platform
capabilities. The current path covers the Vue client, FastAPI/SSE boundary,
LangGraph agent harness, tools and Skills, HITL pause/resume, PostgreSQL state,
hybrid RAG, and offline evaluation.

## Features

### UI and Streaming Interaction

- **Conversation workspace** — Vue 3, Pinia, Ant Design Vue/X, and ECharts
  provide streaming chat, persisted conversation history, Markdown rendering,
  tool-call timeline entries, subagent-routing visibility, and chart output.
- **SSE event contract** — FastAPI streams assistant chunks, tool starts and
  results, routing events, interruptions, completion, and safe error events;
  the client maps each event into explicit UI state.
- **Human-in-the-loop UI** — input-mode interruptions request missing business
  fields; approval-mode interruptions present approve/reject controls for
  consequential actions. Both resume the original thread rather than starting
  a new turn.
- **Controlled chart output** — procurement analysis agents emit only
  schema-validated, single-line chart JSON. The server rejects arbitrary HTML,
  images, and ECharts options; the client deterministically renders supported
  chart types from the validated payload. See [`Chart-Output-Practical.md`](backend/docs/chart-render/Chart-Output-Practical.md).

### Agent Runtime and Orchestration

- **Deep Agents on LangGraph** — a primary procurement agent is compiled with
  checkpoints, durable store access, filesystem tools, Skills, middleware, and
  subagent delegation.
- **Declarative subagents** — procurement analysis, procurement order, and
  supplier-management agents are loaded from validated YAML definitions. Each
  definition owns its prompt, tool allowlist, additional Skills, and HITL rules.
- **Planning and task control** — the Deep Agents harness supplies `write_todos`
  for multi-step planning, alongside built-in filesystem operations such as
  `read_file`, `write_file`, `edit_file`, directory listing, search, and glob.
- **Resumable execution** — LangGraph interrupts retain the exact checkpoint
  namespace and frontend contract. Resume requests accept either free-text tool
  input or structured approval decisions.
- **Human approval for writes** — supplier and procurement-order creation or
  updates pause through `interrupt_on` before the Motorparts HTTP request. Only an
  approval submits the mutation; rejection explicitly leaves Motorparts state intact.
  See [`HITL-Approval-Practical.md`](backend/docs/hitl/HITL-Approval-Practical.md).

### Context Engineering and Memory

- **Request-scoped context assembly** — each run receives user identity, user
  name, time, and retrieval context. Retrieved documents are explicitly
  delimited as untrusted reference material and retain their source IDs.
- **Automatic context-window management** — Deep Agents automatically
  summarizes long conversations when a model exposes `max_input_tokens`; the
  default trigger is 85% of the context window and keeps 10%. For models without
  a profile, the runtime uses its conservative fixed-token fallback. See [`Memory-Practical.md`](backend/docs/memory/Memory-Practical.md).
- **Recoverable conversation compaction** — before automatic summarization,
  evicted history is offloaded to the configured backend and the summary keeps a
  path that the agent can reopen with `read_file`. See [`Memory-Practical.md`](backend/docs/memory/Memory-Practical.md).
- **Long-term user memory** — durable memory is scoped by agent and user in
  PostgreSQL, so preferences survive across that user's threads without crossing
  user boundaries. Bundled operating guidance remains separate and read-only.
  See [`Memory-Practical.md`](backend/docs/memory/Memory-Practical.md).
- **Layered filesystem permissions** — shared `/memory/` guidance and `/skills/`
  are write-denied, while user long-term memory under `/memories/` is readable
  and writable. These permissions govern built-in file tools separately from
  execution sandboxing. See [`Filesystem-Permission-Practical.md`](backend/docs/memory/Filesystem-Permission-Practical.md).
- **Portable execution-sandbox boundary** — procurement-analysis `execute` is
  currently used for internal aggregation, controlled chart output, and report
  generation; the architecture reserves AIO Sandbox for process, network,
  resource, and temporary-file isolation. See [`Sandbox-Practical.md`](backend/docs/memory/Sandbox-Practical.md).

### Tools, Files, and Skills

- **Bounded Motorparts tools** — typed registered tools use a shared HTTP client for
  suppliers, parts, orders, inventory, logistics, customers, BI, and knowledge
  retrieval. The system prompt requires Motorparts facts to come from these tools.
- **Large-result offloading** — the Deep Agents filesystem middleware evicts
  oversized tool results to files and returns a compact reference; agents can
  inspect the full result incrementally with `read_file` and offsets.
- **Structured report delivery** — the procurement-analysis Skill reads its
  chart contract before visual work and writes complex reports to a file,
  returning a concise summary and path for the parent agent to read back.
- **Progressive-disclosure Skills** — versioned `SKILL.md` instructions are
  mounted under `/skills/`; static Skills and policy guidance are write-denied,
  while user memory under `/memories/` remains writable.
- **Workflow-oriented Skill architecture** — Memory fixes global rules, Skills
  load domain procedures and contracts on demand, Tools perform atomic actions,
  and RAG supplies document knowledge without permanently expanding the primary
  prompt with every workflow. See [`Skill-Architecture-Practical.md`](backend/docs/skills/Skill-Architecture-Practical.md).

### Hybrid RAG and Context Quality

- **Three-angle query rewriting** — semantic, keyword, and intent rewrites run
  alongside the original query to improve candidate hit rate and recall before
  hybrid retrieval. See [`Query-Rewrite-Practical.md`](backend/docs/rag/Query-Rewrite-Practical.md).
- **Hybrid ranking pipeline** — dense and BM25 channels are fused with weighted
  reciprocal-rank fusion, collapsed through parent-document expansion, and
  optionally reranked with FlagEmbedding before context injection.
- **Grounded context boundary** — the selected passages are marked as
  untrusted, carry source identifiers, and are separated from the system
  instruction to reduce retrieval-induced prompt injection.

### Guardrails, State, and Observability

- **Runtime middleware** — prompt-injection detection, PII redaction or
  masking for email, phone, ID card, credit-card, and API-key patterns, request
  context injection, and per-thread/per-run tool-call limits are registered with
  the primary agent.
- **RAG defence and context path** — the original query plus three rewrite
  views pass through dense retrieval, BM25, weighted RRF, and reranking.
  Middleware presents the resulting context as untrusted reference content and
  protects model and tool calls against injection, PII, and excessive calls.
  See [`RAG-Agent-Middleware-Defense-and-Context.md`](backend/docs/middleware/RAG-Agent-Middleware-Defense-and-Context.md).
- **State and auditability foundation** — PostgreSQL persists LangGraph
  checkpoints, conversation metadata, and the user-visible tool/message
  timeline; it enables interruption recovery and post-run inspection.
- **Tracing-ready debugging** — SSE events retain LangGraph node, step,
  namespace, subagent, and checkpoint metadata, with optional raw debug payloads
  for development. LangSmith tracing and production monitoring are tracked in
  the roadmap rather than presented as complete observability infrastructure.

### Evaluation

- **Offline agent evaluation** — a labelled Motorparts Agent dataset drives the
  production graph with mocked Motorparts fixtures while recording final answers,
  selected tools, retrieved contexts, tool evidence, errors, and latency.
- **RAGAS quality metrics** — faithfulness, answer relevancy, context precision,
  context recall, and answer correctness are scored by an optional LLM judge;
  tool correctness is calculated separately from expected and observed tools.
- **Diagnostic regression evaluation** — evaluations reuse the production agent
  orchestration with read-only Motorparts fixtures, retaining answers, retrieval
  evidence, tool traces, errors, and latency to distinguish retrieval, tool
  selection, and generation failures. See [`Ragas-Agent-Evaluation-Practical.md`](backend/docs/evals/Ragas-Agent-Evaluation-Practical.md).

## Core Workflows

### Procurement Analysis

The primary agent receives a procurement question, delegates specialised work
when appropriate, retrieves Motorparts or knowledge-base evidence, and streams a
grounded response. Structured chart data can be rendered by the frontend.

### Information Collection and Approval

An order or supplier subagent either asks for missing fields or prepares a
mutation. LangGraph pauses before the Motorparts request, the UI collects a response or
decision, and the same thread resumes from its PostgreSQL checkpoint.

### Retrieval-Augmented Assistance

The request is rewritten from several perspectives. Dense and sparse results
are fused with weighted RRF, expanded to parent documents, optionally reranked,
and delimited with source identifiers before entering the model context.

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Agent runtime | Python 3.12, Deep Agents, LangGraph, LangChain |
| API and transport | FastAPI, SSE Starlette, HTTPX |
| State and memory | PostgreSQL, Psycopg, LangGraph PostgreSQL checkpoint/store |
| Retrieval | Milvus/Zilliz, dense retrieval, BM25, RRF, FlagEmbedding reranking |
| Evaluation | RAGAS, pytest, offline trace runner |
| Client | Vue 3, TypeScript, Vite, Pinia, Ant Design Vue/X, ECharts |

## Quick Start

### Prerequisites

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/)
- Node.js and [pnpm](https://pnpm.io/)
- PostgreSQL
- An OpenAI-compatible model endpoint and API key

### Start the Backend

```powershell
cd backend
Copy-Item .env.example .env
# Configure the core database, model, and Motorparts API values in .env (see below).
uv sync
uv run uvicorn src.api_view.web_main:app --reload --port 8000
```

At minimum, set `DATABASE_URL`, `MOTORPARTS_MODEL_BASE_URL`,
`MOTORPARTS_MODEL_API_KEY`, `MOTORPARTS_AGENT_MODEL`, and
`MOTORPARTS_API_BASE_URL`. Set `MOTORPARTS_API_TOKEN` when the Motorparts
service requires authentication. To use hybrid RAG, configure `ZILLIZ_URI`,
`ZILLIZ_TOKEN`, and `MILVUS_COLLECTION` together. Because `.env.example`
enables LangSmith tracing, also provide `LANGSMITH_API_KEY` or set
`LANGSMITH_TRACING=false`.

The backend starts on `http://localhost:8000`. Hybrid RAG is optional and is
enabled when the Milvus/Zilliz connection settings are configured.

### Start the Frontend

```powershell
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`. During development, Vite proxies API requests to
the backend at port 8000.

## Screenshots

| ![Knowledge search and retrieval-assisted answer](docs/images/screenshots/search_knowdge.png)Streaming chat and retrieved knowledge context. | ![Prompt-injection detection in the chat workflow](docs/images/screenshots/promptInjection2.png)Runtime prompt-injection detection. | ![Controlled chart output](docs/images/screenshots/chart_render.png)Validated chart rendering. |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| ![Human-in-the-loop approval flow](docs/images/screenshots/hitl.png)Approval before a consequential write. | ![Request context injection in a LangSmith trace](docs/images/screenshots/langsmith_trace_request_context_injection.png)Request context in trace metadata. | ![Prompt-injection trace in LangSmith](docs/images/screenshots/promptInjection_langsmith.png)Guardrail decisions in LangSmith. |

## Documentation

### Practical Guides

- [`backend/ARCH.md`](backend/ARCH.md)  Backend architecture notes.
- [`backend/docs/chart-render/Chart-Output-Practical.md`](backend/docs/chart-render/Chart-Output-Practical.md)  Controlled chart-data contract and frontend rendering boundary.
- [`backend/docs/evals/Ragas-Agent-Evaluation-Practical.md`](backend/docs/evals/Ragas-Agent-Evaluation-Practical.md)  RAGAS metrics, tool correctness, and regression diagnosis.
- [`backend/docs/hitl/HITL-Approval-Practical.md`](backend/docs/hitl/HITL-Approval-Practical.md)  Motorparts write interruption, approval, and resume flow.
- [`backend/docs/memory/Filesystem-Permission-Practical.md`](backend/docs/memory/Filesystem-Permission-Practical.md)  Permission boundaries for Deep Agents built-in filesystem tools.
- [`backend/docs/memory/Memory-Practical.md`](backend/docs/memory/Memory-Practical.md)  Conversation summaries, durable user memory, and isolation.
- [`backend/docs/memory/Sandbox-Practical.md`](backend/docs/memory/Sandbox-Practical.md)  `execute` isolation and AIO Sandbox migration design.
- [`backend/docs/middleware/RAG-Agent-Middleware-Defense-and-Context.md`](backend/docs/middleware/RAG-Agent-Middleware-Defense-and-Context.md)  Query, context injection, prompt-injection, and PII defence path.
- [`backend/docs/rag/Query-Rewrite-Practical.md`](backend/docs/rag/Query-Rewrite-Practical.md)  Four-view query rewriting and hybrid retrieval practice.
- [`backend/docs/skills/Skill-Architecture-Practical.md`](backend/docs/skills/Skill-Architecture-Practical.md)  Responsibilities across Memory, Skills, Tools, and RAG.

## Roadmap

- Refactor and migrate the frontend to [assistant-ui](https://github.com/assistant-ui/assistant-ui), whose native LangChain and LangGraph support better aligns with the backend runtime.
- Production-grade authentication and authorization.
- LangSmith tracing, operational monitoring, and cost visibility.
- Containerized deployment and environment orchestration.
- **AIO Sandbox migration** — migrate procurement analysis from the current
  `local_shell` backend to [agent-infra/sandbox](https://github.com/agent-infra/sandbox)
  for isolated process, network, dependency, resource, and temporary-file
  boundaries.
- Stronger empty-response, rate-limit, retry, and fallback handling.
- Cost-aware evaluation reporting and broader regression coverage.
- GraphRAG integration and prompt versioning through LangSmith or Langfuse.
- Text2SQL, deep research, knowledge-base administration, and visible
  reasoning/planning workflows.

## License

This project is licensed under the [MIT License](LICENSE).
