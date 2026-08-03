# Motorparts Agent Skills Guide

Use the registered tools only:

- `get_dashboard` reads the reviewed procurement dashboard endpoint.
- `create_supplier` is the only active create action and requires human approval
  through the native Deep Agents interrupt before it can execute.
- `run_bi_text2sql` is reserved for BI questions and may report that the
  workflow is not configured.
- `web_search` is available only when its provider configuration is present.

Do not infer API access from a domain directory. A new tool must be added to
the reviewed registry before it is available to the agent or a subagent.
