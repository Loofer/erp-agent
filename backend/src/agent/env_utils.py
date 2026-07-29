"""Environment access helpers for agent runtime configuration."""

import os


def optional_environment_value(name: str) -> str | None:
    """Return a non-empty environment value without persisting secrets."""
    value = os.getenv(name)
    return value or None
