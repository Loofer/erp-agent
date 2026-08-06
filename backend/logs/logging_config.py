"""Centralized logging configuration for console and file."""

import logging
from pathlib import Path

from backend.configs.settings import load_settings

# Backend directory (backend/utils -> backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging() -> None:
    """
    Configure root logger to log to both console (stderr) and a file.
    Log level and file path come from settings (LOG_LEVEL, LOG_FILE).
    """
    settings = load_settings()
    root = logging.getLogger()
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    root.setLevel(level)

    # Avoid adding duplicate handlers if setup_logging() is called more than once
    if root.handlers:
        return

    formatter = logging.Formatter(LOG_FORMAT)

    # logging.config.dictConfig(
    #     {
    #         "version": 1,
    #         "disable_existing_loggers": False,  # keep uvicorn's own loggers intact
    #         "formatters": {
    #             "default": {
    #                 "format": "%(asctime)s %(name)s [%(levelname)s] %(message)s",
    #                 "datefmt": "%Y-%m-%d %H:%M:%S",
    #             }
    #         },
    #         "handlers": {
    #             "console": {
    #                 "class": "logging.StreamHandler",
    #                 "formatter": "default",
    #                 "stream": "ext://sys.stdout",
    #             }
    #         },
    #         "loggers": {
    #             # --- framework loggers we care about ---
    #             "deepagents": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
    #             "langgraph": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
    #             "langchain": {"level": "INFO", "handlers": ["console"], "propagate": False},
    #             # --- uvicorn — keep its existing level, just normalise the format ---
    #             "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
    #             "uvicorn.error": {"level": "INFO", "handlers": ["console"], "propagate": False},
    #             "uvicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},
    #         },
    #         "root": {"level": "INFO", "handlers": ["console"]},
    #     }
    # )


    # Console (stderr)
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File: default backend/logs/app.log unless LOG_FILE is set (use "" to disable file logging)
    log_file = getattr(settings, "log_file", None)
    if log_file is None:
        log_path = BACKEND_DIR / "logs" / "app.log"
    elif log_file == "":
        log_path = None
    else:
        log_path = Path(log_file)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)