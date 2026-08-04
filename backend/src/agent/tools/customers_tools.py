"""Extension boundary for future reviewed customer-domain tools."""

from langchain_core.tools import BaseTool


def build_customer_tools() -> list[BaseTool]:
    """Return no customer tools until the domain is implemented."""
    return []
