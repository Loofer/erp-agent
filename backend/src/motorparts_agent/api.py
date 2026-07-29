"""FastAPI entry point for health checks and future graph invocation."""

from fastapi import FastAPI

app = FastAPI(title="Motorparts Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
