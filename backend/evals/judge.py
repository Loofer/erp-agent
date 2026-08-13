"""Ragas metrics used by the offline Agent evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.configs.settings import Settings

RAGAS_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
)


@dataclass(frozen=True)
class MetricScore:
    value: float | None
    reason: str
    error: str | None = None


class RagasJudge:
    """Score responses with the five standard LLM-based Ragas metrics."""

    def __init__(self, settings: Settings) -> None:
        try:
            from openai import AsyncOpenAI
            from ragas.embeddings import OpenAIEmbeddings
            from ragas.llms import llm_factory
            from ragas.metrics.collections import (
                AnswerCorrectness,
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                Faithfulness,
            )
        except ImportError as exc:  # pragma: no cover - CLI setup failure
            raise RuntimeError(
                "Install dependencies with uv sync --project backend --extra evals."
            ) from exc

        if not settings.ragas_judge_api_key:
            raise ValueError("RAGAS_JUDGE_API_KEY must be configured.")
        client = AsyncOpenAI(
            api_key=settings.ragas_judge_api_key.get_secret_value(),
            base_url=settings.ragas_judge_base_url or None,
        )
        llm = llm_factory(
            settings.ragas_judge_model,
            provider="openai",
            client=client,
        )
        embeddings = OpenAIEmbeddings(
            client=client,
            model=settings.ragas_judge_embedding_model,
        )
        self._metrics = {
            "faithfulness": Faithfulness(llm=llm),
            "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
            "context_precision": ContextPrecision(llm=llm),
            "context_recall": ContextRecall(llm=llm),
            "answer_correctness": AnswerCorrectness(llm=llm, embeddings=embeddings),
        }

    async def score(self, sample: dict[str, Any]) -> dict[str, MetricScore]:
        common = {
            "user_input": str(sample["input"]),
            "response": str(sample.get("response", "")),
            "reference": str(sample["reference_answer"]),
            "retrieved_contexts": [
                str(item) for item in sample.get("retrieved_contexts", [])
            ],
        }
        calls = {
            "faithfulness": {
                key: common[key]
                for key in ("user_input", "response", "retrieved_contexts")
            },
            "answer_relevancy": {
                key: common[key] for key in ("user_input", "response")
            },
            "context_precision": {
                key: common[key]
                for key in ("user_input", "reference", "retrieved_contexts")
            },
            "context_recall": {
                key: common[key]
                for key in ("user_input", "reference", "retrieved_contexts")
            },
            "answer_correctness": {
                key: common[key] for key in ("user_input", "response", "reference")
            },
        }
        results: dict[str, MetricScore] = {}
        for name in RAGAS_METRICS:
            results[name] = await self._score(self._metrics[name], **calls[name])
        return results

    async def _score(self, metric: Any, **kwargs: object) -> MetricScore:
        try:
            result = await metric.ascore(**kwargs)
            return MetricScore(
                value=round(float(result.value), 4),
                reason=str(getattr(result, "reason", "")),
            )
        except Exception as exc:  # noqa: BLE001
            return MetricScore(value=None, reason="Metric failed", error=str(exc))


def tool_correctness(expected_tools: list[str], actual_tools: list[str]) -> float:
    """Return Jaccard similarity for expected and observed business tools."""
    expected = set(expected_tools)
    actual = set(actual_tools) - {"task"}
    union = expected | actual
    return round(len(expected & actual) / len(union), 4) if union else 1.0
