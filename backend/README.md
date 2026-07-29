# Motorparts Agent Backend

Runnable backend skeleton for the motor-parts procurement agent.

## Development

```powershell
uv run pytest -v
uv run ruff check .
```

The only active read operation is `getDashboard`. Supplier creation is staged as
a pending action and must be approved before an HTTP request is sent.
