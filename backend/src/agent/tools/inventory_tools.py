"""Extension boundary for future reviewed inventory-domain tools."""

from langchain_core.tools import BaseTool


def build_inventory_tools() -> list[BaseTool]:
    """Return no tools until an inventory Swagger operation is approved."""
    return []
