"""Extension boundary for future reviewed parts-domain tools."""

from langchain_core.tools import BaseTool


def build_part_tools() -> list[BaseTool]:
    """Return no tools until a parts Swagger operation is explicitly approved."""
    return []
