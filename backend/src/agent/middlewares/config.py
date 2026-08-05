"""Deep Agents middleware configuration."""

from .rag_context import RequestContextPromptMiddleware


def build_runtime_middlewares() -> list[object]:
    """Return request-context middleware after Deep Agents built-ins."""
    return [RequestContextPromptMiddleware()]
