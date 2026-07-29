"""Logging helpers for agent runtime components."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return the named application logger without configuring global handlers."""
    return logging.getLogger(name)
