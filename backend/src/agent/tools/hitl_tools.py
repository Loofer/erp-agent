"""Human-input tools used by declarative workflow subagents."""

from langchain_core.tools import BaseTool, tool

def build_hitl_tools() -> list[BaseTool]:
    """Return normal tools whose calls require native human intervention."""
    return []
