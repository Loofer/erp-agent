"""CLI entry point for the lightweight Agent evaluation."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean

from .judge import RAGAS_METRICS
from .runner import DEFAULT_DATASET, load_dataset, run_sync

METRIC_DISPLAY_NAMES = {
    "faithfulness": "Exp 1  Faithfulness",
    "answer_relevancy": "Exp 2  Answer Relevancy",
    "context_precision": "Exp 3  Context Precision",
    "context_recall": "Exp 4  Context Recall",
    "answer_correctness": "Exp 5  Answer Correctness",
    "tool_correctness": "Exp 6  Tool Correctness",
}

CSV_FIELDS = [
    "id",
    "category",
    "input",
    "model",
    "response",
    "expected_tools",
    "actual_tools",
    "retrieved_ids",
    "retrieved_contexts",
    *METRIC_DISPLAY_NAMES,
    *[f"{name}_reason" for name in RAGAS_METRICS],
    "latency_ms",
    "agent_error",
    "judge_error",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ERP Agent Ragas evaluation.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-judge", action="store_true", help="Collect traces without calling Ragas Judge.")
    args = parser.parse_args()
    results = run_sync(load_dataset(args.dataset), use_judge=not args.no_judge)
    output = args.output or Path(__file__).parent / "experiments" / f"run-{datetime.now(UTC):%Y%m%d-%H%M%S}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    key: row.get(key, "")
                    if not isinstance(row.get(key, ""), (list, dict))
                    else str(row.get(key))
                    for key in CSV_FIELDS
                }
            )
    total = len(results)
    errors = sum(bool(row.get("agent_error") or row.get("judge_error")) for row in results)
    print(f"Evaluated {total} samples; errors={errors}")
    for name, display_name in METRIC_DISPLAY_NAMES.items():
        values = [float(row[name]) for row in results if row.get(name) is not None]
        average = f"{fmean(values):.3f}" if values else "n/a"
        print(f"{display_name}: {average}")
    print(f"Results saved to {output}")


if __name__ == "__main__":
    main()
