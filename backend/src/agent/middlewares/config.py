"""Extension point for future Deep Agents middleware configuration."""


def build_runtime_middlewares() -> list[object]:
    """Return no custom middleware while native HITL is sufficient."""
    return []
