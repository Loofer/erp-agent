"""FastAPI application composition and chat-runtime lifecycle."""

import logging
import logging.config
from contextlib import asynccontextmanager

# ---------------------------------------------------------------------------
# Logging — applied at import time, AFTER uvicorn has set up its own handlers.
# dictConfig always takes effect regardless of pre-existing handler state;
# basicConfig would silently do nothing once uvicorn touches the root logger.
# ---------------------------------------------------------------------------
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,  # keep uvicorn's own loggers intact
        "formatters": {
            "default": {
                "format": "%(asctime)s %(name)s [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            # --- framework loggers we care about ---
            "deepagents": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
            "langgraph":  {"level": "DEBUG", "handlers": ["console"], "propagate": False},
            "langchain":  {"level": "INFO",  "handlers": ["console"], "propagate": False},
            # --- uvicorn — keep its existing level, just normalise the format ---
            "uvicorn":        {"level": "INFO", "handlers": ["console"], "propagate": False},
            "uvicorn.error":  {"level": "INFO", "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
)

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore

from agent.config import load_settings
from agent.main_agent import load_agent_graph

from .chat import router as chat_router
from .chat_persistence import ConversationRepository
from .chat_service import ChatService

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open shared persistence and build the agent graph before accepting requests.

    Eager initialisation (rather than a lazy factory) means:
    - deepagents / langgraph startup logs appear in the console at boot time.
    - Configuration errors surface immediately instead of on the first request.
    """
    settings = load_settings()

    with PostgresStore.from_conn_string(settings.database_url) as store:
        store.setup()
        async with AsyncPostgresSaver.from_conn_string(
            settings.database_url
        ) as checkpointer:
            await checkpointer.setup()
            conversations = ConversationRepository(checkpointer.conn)
            await conversations.setup()

            _log.info("Initialising agent graph …")
            graph = load_agent_graph(checkpointer=checkpointer, store=store)
            _log.info("Agent graph ready.")

            app.state.chat_service = ChatService(
                graph,
                conversations,
                agent_id=settings.agent_id,
            )
            yield


app = FastAPI(title="Motorparts Agent", lifespan=lifespan)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
