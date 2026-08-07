"""Tool registry for declarative subagents."""

from langchain_core.tools import BaseTool

from .hitl_tools import build_hitl_tools
from .http_base import ApiClient
from .inventory_tools import build_inventory_tools
from .orders_tools import build_order_tools
from .parts_tools import build_part_tools
from .suppliers_tools import build_supplier_tools


def build_subagent_only_tools(client: ApiClient) -> list[BaseTool]:
    """Build tools that only declarative subagents can receive by name."""
    return [
        *build_supplier_tools(client),
        *build_part_tools(client),
        *build_inventory_tools(client),
        *build_order_tools(client),
        *build_hitl_tools(),
    ]
