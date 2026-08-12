"""Public chart payload builder shared by streaming and history APIs."""

from typing import Any

from .echarts import chart_spec_to_echarts_option
from .schema import ChartSpec


def build_chart_payload(spec: ChartSpec) -> dict[str, Any]:
    """Build a browser-safe payload from an already validated chart specification."""
    option = chart_spec_to_echarts_option(spec)
    reason = None
    if spec.chart_type == "table":
        reason = "table_requested"
    elif spec.chart_type == "kpi":
        reason = "kpi_requested"
    elif not spec.chartable:
        reason = "not_chartable"
    return {
        "requested": True,
        "spec": spec.model_dump(mode="json"),
        "echarts": option,
        "reason": reason,
    }
