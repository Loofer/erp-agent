"""Extension boundary for future reviewed customer-domain tools."""

from langchain_core.tools import BaseTool


def build_customer_tools() -> list[BaseTool]:
    """Return no tools until a customer Swagger operation is approved."""
    return []
