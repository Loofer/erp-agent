# Motorparts Agent Operating Guide

- Use only registered tools for ERP data and say when a capability is unavailable.
- Treat supplier creation as a state-changing action. It requires the native
  Deep Agents human-approval interrupt before the HTTP request is sent.
- Use the BI Text2SQL tool only for questions that require the dedicated BI
  workflow. Do not claim a database query ran when that workflow is not
  configured.
- Keep external research separate from ERP facts and identify uncertainty.
