"""FastAPI application composition and chat-runtime lifecycle."""

import asyncio
import logging.config
from contextlib import asynccontextmanager

from backend.configs.settings import load_settings
from backend.logs.logging_config import setup_logging

# ---------------------------------------------------------------------------
# Logging — applied at import time, AFTER uvicorn has set up its own handlers.
# dictConfig always takes effect regardless of pre-existing handler state;
# basicConfig would silently do nothing once uvicorn touches the root logger.
# ---------------------------------------------------------------------------
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore

from agent.main_agent import load_agent_graph
from agent.rag.runtime import build_hybrid_retriever
from agent.sandbox import create_modal_backend, create_modal_sandbox

from .auth import JwtIdentityMiddleware
from .chat import router as chat_router
from .chat_persistence import ConversationRepository
from .chat_service import ChatService

setup_logging()
_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open shared persistence and build the agent graph before accepting requests.

    Eager initialisation (rather than a lazy factory) means:
    - deepagents / langgraph startup logs appear in the console at boot time.
    - Configuration errors surface immediately instead of on the first request.
    """
    settings = load_settings()

    _log.info("Creating Modal Sandbox for app erp-agent.")
    modal_sandbox = await asyncio.to_thread(create_modal_sandbox)
    modal_backend = create_modal_backend(modal_sandbox)
    app.state.modal_sandbox = modal_sandbox
    app.state.modal_backend = modal_backend

    try:
        with PostgresStore.from_conn_string(settings.database_url) as store:
            store.setup()
            async with AsyncPostgresSaver.from_conn_string(
                settings.database_url
            ) as checkpointer:
                await checkpointer.setup()
                conversations = ConversationRepository(checkpointer.conn)
                await conversations.setup()

                rag_retriever = None
                try:
                    rag_retriever = await asyncio.to_thread(
                        build_hybrid_retriever, settings
                    )
                except Exception:  # noqa: BLE001
                    _log.exception("RAG initialisation failed; continuing without retrieval")

                _log.info("Initialising agent graph......")
                graph = await asyncio.to_thread(
                    load_agent_graph,
                    checkpointer=checkpointer,
                    store=store,
                    rag_retriever=rag_retriever,
                    sandbox_backend=modal_backend,
                )
                _log.info("Agent graph ready.")

                app.state.chat_service = ChatService(
                    graph,
                    conversations,
                    agent_id=settings.agent_id,
                    rag_retriever=rag_retriever,
                )
                yield
    finally:
        _log.info("Terminating Modal Sandbox.")
        await asyncio.to_thread(modal_sandbox.terminate, wait=True)


app = FastAPI(title="Motorparts Agent", lifespan=lifespan)
app.add_middleware(JwtIdentityMiddleware)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
