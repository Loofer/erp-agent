"""Extension boundary for future reviewed order-domain tools."""

from langchain_core.tools import BaseTool


def build_order_tools() -> list[BaseTool]:
    """Return no tools until an order Swagger operation is explicitly approved."""
    return []
