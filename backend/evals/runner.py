"""Run the Agent evaluation dataset without starting the web service."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from backend.configs.settings import load_settings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.main_agent import load_agent_graph
from agent.rag.runtime import build_hybrid_retriever
from api_view.chat_service import ChatService

from .fixtures.erp import ErpFixture
from .judge import RAGAS_METRICS, RagasJudge, tool_correctness
from .rag_recording import RecordingRetriever

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "agent_smoke.json"


def load_dataset(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Evaluation dataset must be a non-empty JSON list.")
    required = {
        "id",
        "category",
        "input",
        "reference_answer",
        "expected_tools",
        "required_facts",
        "grading_notes",
    }
    sample_ids: set[str] = set()
    for index, sample in enumerate(data):
        if not isinstance(sample, dict):
            raise TypeError(f"Evaluation sample {index} must be a JSON object.")
        missing = required - sample.keys()
        if missing:
            raise ValueError(
                f"Evaluation sample {index} is missing: {', '.join(sorted(missing))}."
            )
        sample_id = sample["id"]
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"Evaluation sample {index} needs a non-empty id.")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate evaluation sample id: {sample_id}.")
        sample_ids.add(sample_id)
    return data


def extract_trace(events: list[dict[str, object]]) -> dict[str, object]:
    """Extract the final parent answer, business tools, and tool evidence."""
    response_chunks: list[str] = []
    actual_tools: list[str] = []
    tool_contexts: list[str] = []
    agent_error: str | None = None
    for event in events:
        data = event.get("data")
        event_data = data if isinstance(data, dict) else {}
        if (
            event.get("event") == "message_chunk"
            and event.get("agent_name") == "erp-agent"
        ):
            response_chunks.append(str(event_data.get("content", "")))
        if event.get("event") == "tool_call_start":
            name = event_data.get("tool_name")
            if name:
                actual_tools.append(str(name))
        if event.get("event") == "tool_call_end":
            result = event_data.get("result")
            if result and event_data.get("tool_name") != "search_knowdge":
                tool_contexts.append(str(result))
        if event.get("event") == "error":
            agent_error = str(event_data.get("message", "agent error"))
        if event.get("event") == "interrupt":
            agent_error = "unexpected HITL interrupt"
    return {
        "response": "".join(response_chunks).strip(),
        "actual_tools": actual_tools,
        "tool_contexts": tool_contexts,
        "agent_error": agent_error,
    }


async def run_dataset(
    samples: list[dict[str, Any]],
    *,
    use_judge: bool = True,
) -> list[dict[str, Any]]:
    settings = load_settings()
    fixture = ErpFixture()
    client = fixture.client()
    rag_retriever = build_hybrid_retriever(settings)
    if rag_retriever is None:
        raise ValueError(
            "Evaluation requires ZILLIZ_URI, ZILLIZ_TOKEN, and MILVUS_COLLECTION."
        )
    recording = RecordingRetriever(rag_retriever)
    graph = load_agent_graph(
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
        api_client=client,
        rag_retriever=recording,
    )
    # The production graph owns the retriever built from current Zilliz config.
    # ChatService receives it separately so it can inject context before a run.
    retriever = recording
    service = ChatService(
        graph,
        None,
        agent_id=settings.motorparts_agent_id,
        rag_retriever=retriever,
        debug=False,
    )
    judge = RagasJudge(settings) if use_judge else None
    results: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        fixture.requests.clear()
        retriever.last_result = None
        started = time.perf_counter()
        row: dict[str, Any] = {**sample, "model": settings.motorparts_agent_model}
        row["actual_tools"] = []
        row["response"] = ""
        row["agent_error"] = None
        try:
            events = [
                event
                async for event in service.stream(
                    sample["input"],
                    f"eval-{sample['id']}-{index}",
                    "eval-user",
                )
            ]
            row.update(extract_trace(events))
        except Exception as exc:  # noqa: BLE001
            row["agent_error"] = str(exc)
        row["erp_requests"] = list(fixture.requests)
        row.update(retriever.snapshot())
        row["retrieved_contexts"] = [
            *row.get("retrieved_contexts", []),
            *row.get("tool_contexts", []),
        ]
        row["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        row["tool_correctness"] = tool_correctness(
            sample.get("expected_tools", []), row["actual_tools"]
        )
        if judge is not None and row["agent_error"] is None:
            scored = await judge.score(row)
            metric_errors: list[str] = []
            for metric_name in RAGAS_METRICS:
                metric = scored[metric_name]
                row[metric_name] = metric.value
                row[f"{metric_name}_reason"] = metric.reason
                if metric.error:
                    metric_errors.append(f"{metric_name}: {metric.error}")
            row["judge_error"] = " | ".join(metric_errors) or None
        else:
            for metric_name in RAGAS_METRICS:
                row[metric_name] = None
                row[f"{metric_name}_reason"] = "not scored"
            row["judge_error"] = None
        results.append(row)
    return results


def run_sync(samples: list[dict[str, Any]], *, use_judge: bool = True) -> list[dict[str, Any]]:
    return asyncio.run(run_dataset(samples, use_judge=use_judge))
