# Procurement Chart Parameters

This is the machine-oriented chart contract for procurement analysis. The
analysis script may select only the chart types marked as frontend-supported.
It must output chart specifications inside the final `ANALYSIS_RESULT=` JSON
line; it must not generate JavaScript, HTML, image files, or ECharts options.

## Output Envelope

```json
{
  "version": "1.0",
  "status": "ok",
  "summary": {
    "sample_size": 0,
    "sources": ["supplier_query"],
    "metrics": [{"name": "average_price", "value": 12.3, "unit": "CNY"}],
    "data_gaps": []
  },
  "charts": [],
  "report_markdown": "# Procurement Analysis Report"
}
```

Allowed `status` values are `ok`, `partial`, `insufficient_data`, and `error`.
`partial` and `insufficient_data` require a non-empty `summary.data_gaps` list.
Every metric and chart value must be traceable to ERP tool output from the
current task. Never estimate missing values.

## Frontend-Supported Charts

| chart_type | Required fields | Use | frontend_supported |
| --- | --- | --- | --- |
| `bar` | `id`, `title`, `x`, `y`, `data[]` | Category comparison, such as supplier price | true |
| `line` | `id`, `title`, `x`, `y`, `data[]` | Ordered time or sequence trend | true |
| `pie` | `id`, `title`, `x`, `y`, `data[]` | Composition with a small number of categories | true |
| `table` | `id`, `title`, `data[]` | Detailed rows or a fallback for unsuitable charts | true |
| `kpi` | `id`, `title`, `data[]` | Small set of headline metrics | true |
| `radar`, `histogram`, `treemap`, `network_graph`, `boxplot`, `waterfall`, `liquid`, `funnel` | N/A | Not supported in the first release | false |

`data` is an array of objects with at most 500 rows. For `bar`, `line`, and
`pie`, the `x` and `y` fields must exist in every relevant row. Include
`provenance` with the ERP tool names used and `warnings` for any limitations.

## Chart Specification Examples

```json
{
  "id": "supplier-price-comparison",
  "chart_type": "bar",
  "title": "Supplier average price comparison",
  "x": "supplier_name",
  "y": "average_price",
  "data": [{"supplier_name": "Supplier A", "average_price": 12.3}],
  "provenance": ["supplier_query", "order_search_details"],
  "warnings": []
}
```

When data cannot support a chart, use `table` or omit the chart and explain the
gap in `summary.data_gaps`. Do not emit an unsupported chart type.
