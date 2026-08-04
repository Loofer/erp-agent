"""Extension boundary for future reviewed logistics-domain tools."""

from langchain_core.tools import BaseTool


def build_logistics_tools() -> list[BaseTool]:
    """Return no logistics tools until the domain is implemented."""
    return []
