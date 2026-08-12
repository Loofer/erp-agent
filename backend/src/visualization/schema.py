"""Validation models for the structured procurement-analysis output."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ChartType = Literal["bar", "line", "pie", "table", "kpi"]
AnalysisStatus = Literal["ok", "partial", "insufficient_data", "error"]


class Metric(BaseModel):
    """One reported metric, kept deliberately presentation-neutral."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    value: str | int | float | None = None
    unit: str | None = Field(default=None, max_length=40)


class AnalysisSummary(BaseModel):
    """Facts the UI can show without reinterpreting an analysis script."""

    model_config = ConfigDict(extra="forbid")

    sample_size: int = Field(ge=0)
    sources: list[str] = Field(default_factory=list, max_length=30)
    metrics: list[Metric] = Field(default_factory=list, max_length=30)
    data_gaps: list[str] = Field(default_factory=list, max_length=30)


class ChartSpec(BaseModel):
    """Safe, deterministic input to the ECharts adapter."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    chart_type: ChartType
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=300)
    x: str | None = Field(default=None, max_length=120)
    y: str | None = Field(default=None, max_length=120)
    data: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    provenance: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    chartable: bool = True

    @field_validator("data")
    @classmethod
    def data_rows_must_be_objects(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in value:
            if len(row) > 30:
                raise ValueError("chart data rows may contain at most 30 fields")
        return value

    def model_post_init(self, __context: Any, /) -> None:
        if self.chart_type in {"bar", "line"} and (not self.x or not self.y):
            raise ValueError(f"{self.chart_type} charts require x and y fields")
        if self.chart_type == "pie" and (not self.x or not self.y):
            raise ValueError("pie charts require x and y fields")


class AnalysisResult(BaseModel):
    """The only machine-readable portion of execute stdout we consume."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"]
    status: AnalysisStatus
    summary: AnalysisSummary
    charts: list[ChartSpec] = Field(default_factory=list, max_length=12)
    report_markdown: str = Field(default="", max_length=100_000)

    def model_post_init(self, __context: Any, /) -> None:
        if self.status in {"partial", "insufficient_data"} and not self.summary.data_gaps:
            raise ValueError(f"{self.status} analysis requires data_gaps")


class AnalysisResultError(ValueError):
    """Raised when execute output does not contain a valid analysis document."""


def parse_analysis_result(stdout: object) -> AnalysisResult:
    """Extract the final ``ANALYSIS_RESULT=`` line without parsing arbitrary stdout."""
    if not isinstance(stdout, str):
        raise AnalysisResultError("execute result is not text")

    marker = "ANALYSIS_RESULT="
    candidates = [line[len(marker) :] for line in stdout.splitlines() if line.startswith(marker)]
    if not candidates:
        raise AnalysisResultError("ANALYSIS_RESULT marker is missing")
    try:
        document = json.loads(candidates[-1])
    except json.JSONDecodeError as error:
        raise AnalysisResultError("ANALYSIS_RESULT is not valid JSON") from error
    if isinstance(document, dict):
        # Accept the nested ``charts[].spec`` shape used by older procurement
        # prompts while exposing one canonical ChartSpec to the rest of the app.
        normalized = dict(document)
        charts = []
        for raw_chart in document.get("charts", []) if isinstance(document.get("charts"), list) else []:
            if not isinstance(raw_chart, dict):
                charts.append(raw_chart)
                continue
            chart = dict(raw_chart)
            nested = chart.pop("spec", None)
            if isinstance(nested, dict):
                merged = {**nested, **chart}
                charts.append(merged)
            else:
                charts.append(chart)
        normalized["charts"] = charts
        # Unsupported charts are deliberately downgraded to a bounded table;
        # this keeps the analysis useful without emitting an invalid ECharts option.
        supported = {"bar", "line", "pie", "table", "kpi"}
        normalized["charts"] = [
            (
                {
                    **chart,
                    "chart_type": "table",
                    "warnings": [
                        *(
                            chart.get("warnings", [])
                            if isinstance(chart.get("warnings"), list)
                            else []
                        ),
                        "unsupported_chart_type",
                    ],
                }
                if isinstance(chart, dict) and chart.get("chart_type") not in supported
                else chart
            )
            for chart in normalized["charts"]
        ]
    else:
        normalized = document
    try:
        return AnalysisResult.model_validate(normalized)
    except ValidationError as error:
        raise AnalysisResultError("ANALYSIS_RESULT does not match the v1.0 schema") from error
