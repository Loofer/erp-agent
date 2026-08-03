---
name: procurement-analysis
description: Analyze procurement dashboard data and use the configured BI workflow when needed.
---

# Procurement Analysis

For a procurement status question, call `get_dashboard` and summarize the
returned fields without inventing unavailable metrics. For a question requiring
SQL-style BI analysis, call `run_bi_text2sql`; explain its configured status if
it cannot produce a query result.

Separate externally researched context from ERP data and mark uncertainty.
