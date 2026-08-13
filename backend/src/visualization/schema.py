"""Validation models for optional chart documents emitted by ``execute``."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ChartType = Literal["bar", "line", "pie", "table", "kpi"]


class ChartSpec(BaseModel):
    """Safe, presentation-neutral input to the ECharts adapter."""

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
    def validate_data_rows(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if len(row) > 30:
                raise ValueError("chart data rows may contain at most 30 fields")
        return rows

    def model_post_init(self, __context: Any, /) -> None:
        if self.chart_type in {"bar", "line", "pie"}:
            if not self.x or not self.y:
                raise ValueError(f"{self.chart_type} charts require x and y fields")
            if any(self.x not in row or self.y not in row for row in self.data):
                raise ValueError(f"every {self.chart_type} data row requires x and y fields")


class ChartDocument(BaseModel):
    """One optional NDJSON chart document in otherwise arbitrary stdout."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["chart"]
    version: Literal["1.0"]
    charts: list[ChartSpec] = Field(min_length=1, max_length=12)


class ChartDocumentError(ValueError):
    """Raised when an explicitly emitted chart document is invalid."""


def parse_chart_documents(stdout: object) -> list[ChartSpec]:
    """Extract valid chart NDJSON lines while leaving ordinary stdout untouched."""
    if not isinstance(stdout, str):
        return []

    charts: list[ChartSpec] = []
    for line in stdout.splitlines():
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            document = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(document, dict) or document.get("type") != "chart":
            continue
        try:
            parsed = ChartDocument.model_validate(document)
        except ValidationError as error:
            raise ChartDocumentError("chart document does not match the v1.0 schema") from error
        charts.extend(parsed.charts)
    return charts
