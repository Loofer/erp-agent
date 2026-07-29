"""FastAPI entry point for health checks and future graph invocation."""

from fastapi import FastAPI

from .api.chat import router as chat_router
from .api.history import router as history_router

app = FastAPI(title="Motorparts Agent")
app.include_router(chat_router)
app.include_router(history_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
