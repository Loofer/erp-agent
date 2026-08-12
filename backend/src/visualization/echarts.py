"""Deterministic conversion from validated ChartSpec objects to ECharts options."""

from typing import Any

from .schema import ChartSpec

_PALETTE = ["#1677ff", "#13a8a8", "#fa8c16", "#722ed1", "#eb2f96", "#52c41a"]


def chart_spec_to_echarts_option(spec: ChartSpec) -> dict[str, Any] | None:
    """Return a JSON-serializable option, or ``None`` for HTML-only chart types."""
    if not spec.chartable or spec.chart_type in {"table", "kpi"}:
        return None

    base: dict[str, Any] = {
        "color": _PALETTE,
        "tooltip": {"trigger": "axis" if spec.chart_type != "pie" else "item"},
        "title": {"text": spec.title, "subtext": spec.subtitle or ""},
        "grid": {"left": 48, "right": 24, "top": 72, "bottom": 40, "containLabel": True},
    }
    if spec.chart_type in {"bar", "line"}:
        assert spec.x is not None and spec.y is not None
        base.update(
            {
                "xAxis": {"type": "category", "data": [row.get(spec.x, "") for row in spec.data]},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": spec.y,
                        "type": spec.chart_type,
                        "data": [row.get(spec.y) for row in spec.data],
                        "smooth": spec.chart_type == "line",
                    }
                ],
            }
        )
        return base

    assert spec.x is not None and spec.y is not None
    base.update(
        {
            "legend": {"bottom": 0},
            "series": [
                {
                    "name": spec.title,
                    "type": "pie",
                    "radius": ["35%", "68%"],
                    "data": [
                        {"name": row.get(spec.x, ""), "value": row.get(spec.y)}
                        for row in spec.data
                    ],
                }
            ],
        }
    )
    return base
