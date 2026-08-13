# ERP Agent Evaluation

This evaluation runs the production LangGraph Agent orchestration without
starting FastAPI. It uses the configured Zilliz/Milvus collection for RAG and a
fixed, read-only ERP fixture for supplier, part, order, and inventory tools.

## Setup

Install the optional evaluation dependencies:

```powershell
uv sync --project backend --extra evals
```

Configure the normal Agent model and RAG variables, plus a dedicated judge:

```dotenv
RAGAS_JUDGE_API_KEY=
RAGAS_JUDGE_BASE_URL=https://api.openai.com/v1
RAGAS_JUDGE_MODEL=gpt-5.4-mini
RAGAS_JUDGE_EMBEDDING_MODEL=text-embedding-3-small
```

`ZILLIZ_URI`, `ZILLIZ_TOKEN`, and `MILVUS_COLLECTION` are required. The command
fails before running samples when the live RAG index is not configured.

The judge endpoint must support both chat completions and embeddings. Ragas
0.4.3 is paired with `langchain-community>=0.3.31,<0.4` because later community
releases removed an import still used by this Ragas version.

## Run

From the repository root:

```powershell
uv run --project backend --extra evals python -m backend.evals.run
```

Use another dataset or output path when needed:

```powershell
uv run --project backend --extra evals python -m backend.evals.run `
  --dataset backend/evals/datasets/agent_smoke.json `
  --output backend/evals/experiments/manual.csv
```

`--no-judge` runs the Agent and collects traces without calling the five
LLM-based metrics. Tool correctness is still calculated.

## Metrics

The CSV and console summary expose six metrics:

1. `faithfulness`: whether answer claims are supported by retrieved evidence.
2. `answer_relevancy`: whether the answer addresses the user question.
3. `context_precision`: whether retrieved evidence is relevant to the reference.
4. `context_recall`: whether retrieved evidence covers the reference answer.
5. `answer_correctness`: answer similarity and factual correctness versus reference.
6. `tool_correctness`: Jaccard similarity of expected and actual business tools.

`retrieved_contexts` combines Zilliz parent chunks and completed ERP tool
results. This lets the same Ragas metrics evaluate knowledge questions and
read-only ERP questions. Raw RAG IDs, tool names, latency, Agent errors, metric
reasons, and Judge errors are retained for diagnosis.

## Dataset and isolation

The initial dataset contains six reviewed Chinese smoke cases: RAG, supplier,
part, order, inventory, and multi-tool procurement analysis. Add cases to
`evals/datasets/agent_smoke.json` with an input, reference answer, expected
tools, required facts, and grading notes.

The ERP fixture rejects every non-GET request. HITL and mutation evaluation are
out of scope. Zilliz remains live, so RAG scores can change when the collection,
embedding model, query rewriting, or reranker changes.
