import json
from types import SimpleNamespace

import httpx
import pytest

from evals.fixtures.erp import ErpFixture
from evals.judge import RAGAS_METRICS, RagasJudge, tool_correctness
from evals.run import CSV_FIELDS, METRIC_DISPLAY_NAMES
from evals.runner import extract_trace, load_dataset


def test_smoke_dataset_covers_six_read_only_scenarios() -> None:
    samples = load_dataset()

    assert len(samples) == 6
    assert {sample["category"] for sample in samples} == {
        "rag",
        "supplier_query",
        "part_query",
        "order_query",
        "inventory_query",
        "procurement_analysis",
    }
    forbidden = {"create_supplier", "create_order", "update_order"}
    assert all(not forbidden.intersection(sample["expected_tools"]) for sample in samples)


def test_dataset_rejects_duplicate_ids(tmp_path) -> None:
    sample = load_dataset()[0]
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps([sample, sample]), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate evaluation sample id"):
        load_dataset(path)


def test_erp_fixture_records_reads_and_rejects_writes() -> None:
    fixture = ErpFixture()
    client = httpx.Client(base_url="https://erp.fixture", transport=fixture.transport())

    response = client.get("/api/parts/search", params={"name": "BP-100"})
    rejected = client.post("/api/orders/create", json={"partId": 1001})

    assert response.json()["data"][0]["partCode"] == "BP-100"
    assert rejected.status_code == 405
    assert fixture.requests == [
        {
            "method": "GET",
            "path": "/api/parts/search",
            "query": {"name": "BP-100"},
            "body": None,
        },
        {
            "method": "POST",
            "path": "/api/orders/create",
            "query": {},
            "body": {"partId": 1001},
        },
    ]


def test_extract_trace_keeps_parent_answer_tools_and_evidence() -> None:
    events = [
        {
            "event": "message_chunk",
            "agent_name": "procurement_analyst",
            "data": {"content": "internal"},
        },
        {
            "event": "tool_call_start",
            "data": {"tool_name": "inventory_warning"},
        },
        {
            "event": "tool_call_end",
            "data": {"result": '{"currentQuantity": 8}'},
        },
        {
            "event": "message_chunk",
            "agent_name": "erp-agent",
            "data": {"content": "需要补货"},
        },
    ]

    assert extract_trace(events) == {
        "response": "需要补货",
        "actual_tools": ["inventory_warning"],
        "tool_contexts": ['{"currentQuantity": 8}'],
        "agent_error": None,
    }


def test_tool_correctness_uses_jaccard_and_ignores_routing_task() -> None:
    assert tool_correctness(
        ["inventory_warning", "order_search_details"],
        ["task", "inventory_warning", "order_search_details"],
    ) == 1.0
    assert tool_correctness(
        ["inventory_warning", "order_search_details"],
        ["inventory_warning"],
    ) == 0.5


@pytest.mark.anyio
async def test_ragas_judge_passes_metric_specific_inputs() -> None:
    calls: dict[str, dict[str, object]] = {}

    class Metric:
        def __init__(self, name: str) -> None:
            self.name = name

        async def ascore(self, **kwargs: object) -> object:
            calls[self.name] = kwargs
            return SimpleNamespace(value=0.75, reason="ok")

    judge = RagasJudge.__new__(RagasJudge)
    judge._metrics = {name: Metric(name) for name in RAGAS_METRICS}
    result = await judge.score(
        {
            "input": "库存如何？",
            "response": "库存为 8。",
            "reference_answer": "库存为 8。",
            "retrieved_contexts": ["currentQuantity=8"],
        }
    )

    assert set(result) == set(RAGAS_METRICS)
    assert all(score.value == 0.75 for score in result.values())
    assert set(calls["faithfulness"]) == {
        "user_input",
        "response",
        "retrieved_contexts",
    }
    assert set(calls["answer_relevancy"]) == {"user_input", "response"}
    assert set(calls["context_precision"]) == {
        "user_input",
        "reference",
        "retrieved_contexts",
    }
    assert set(calls["context_recall"]) == {
        "user_input",
        "reference",
        "retrieved_contexts",
    }
    assert set(calls["answer_correctness"]) == {
        "user_input",
        "response",
        "reference",
    }


def test_csv_exposes_all_six_metrics() -> None:
    assert tuple(METRIC_DISPLAY_NAMES) == (*RAGAS_METRICS, "tool_correctness")
    assert all(metric in CSV_FIELDS for metric in METRIC_DISPLAY_NAMES)
