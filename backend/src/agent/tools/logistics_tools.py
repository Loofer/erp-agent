"""Extension boundary for future reviewed logistics-domain tools."""

from langchain_core.tools import BaseTool


def build_logistics_tools() -> list[BaseTool]:
    """Return no tools until a logistics Swagger operation is approved."""
    return []
