# Execute Chart Output

Use this contract only when an `execute` script needs the frontend to render charts. Ordinary scripts may print any text and do not need structured output.

Print each chart document as one complete JSON line (NDJSON). Do not assign it to a variable, add a marker prefix, wrap it in Markdown, or emit ECharts/HTML code.

```json
{"type":"chart","version":"1.0","charts":[{"id":"supplier-price","chart_type":"bar","title":"供应商平均采购价","x":"supplier_name","y":"average_price","data":[{"supplier_name":"供应商A","average_price":12.3}],"provenance":["order_search_details"],"warnings":[]}]}
```

## Python output

Use any suitable `execute` workflow. Ensure Python prints the chart document as one compact JSON line:


Do not add backslashes before quotes in Python expressions. Write `row['supplier_name']`, not `row[\'supplier_name\']`; the latter causes a `SyntaxError`.

## Supported charts

| `chart_type` | Required fields | Use |
| --- | --- | --- |
| `bar` | `id`, `title`, `x`, `y`, `data` | Category comparison |
| `line` | `id`, `title`, `x`, `y`, `data` | Ordered trends |
| `pie` | `id`, `title`, `x`, `y`, `data` | Composition with few categories |
| `table` | `id`, `title`, `data` | Detailed rows or chart fallback |
| `kpi` | `id`, `title`, `data` | Headline metrics |

For `bar`, `line`, and `pie`, every data row must contain the fields named by `x` and `y`. Keep each chart at 500 rows or fewer. Include the ERP tool names in `provenance`; put data limitations in `warnings`. Emit at most 12 charts per document.

Do not emit unsupported chart types. Omit a chart when the data cannot support it and explain the limitation in the Agent's response or report.

This protocol transports charts only. Do not include analysis status, summaries, report Markdown, or file paths. Return a simple report in the Agent response; create a complex report with `write_file`.
