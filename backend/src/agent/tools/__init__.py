"""Explicit parent and subagent tool registries for the motor-parts API."""

from langchain_core.tools import BaseTool

from .hitl_tools import build_hitl_tools
from .http_base import ApiClient
from .openapi import Operation
from .statistics_tools import build_statistics_tools
from .suppliers_tools import build_supplier_tools


def build_parent_tools(
    catalog: dict[str, Operation], client: ApiClient
) -> list[BaseTool]:
    """Build tools available directly to the primary Deep Agent."""
    return [
        *build_statistics_tools(catalog, client),
    ]


def build_subagent_only_tools(
    catalog: dict[str, Operation], client: ApiClient
) -> list[BaseTool]:
    """Build tools that only declarative subagents can receive by name."""
    return [
        *build_supplier_tools(catalog, client),
        *build_hitl_tools(),
    ]
