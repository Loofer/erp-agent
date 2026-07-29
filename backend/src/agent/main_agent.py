"""Deep Agents runtime construction for the motor-parts agent."""

from pathlib import Path

import deepagents
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from .config import load_settings
from .subagents.loader import SubagentDefinition, to_deep_agent_subagents
from .tools.api_client import ApiClient
from .tools.bi_tools import run_bi_text2sql
from .tools.erp_tools import build_erp_tools
from .tools.openapi import load_operation_catalog
from .tools.research_tools import web_search

SYSTEM_PROMPT = (
    "You are a motor-parts procurement assistant. Use only the provided tools "
    "for ERP data and explain when a capability is not configured."
)


def create_main_agent(
    model: str,
    *,
    subagents: tuple[SubagentDefinition, ...],
    api_client: ApiClient | None = None,
) -> CompiledStateGraph:
    """Build the primary Deep Agents runtime from declarative configuration."""
    settings = load_settings()
    contract_path = Path(__file__).resolve().parents[2] / "openapi" / "swagger.json"
    catalog = load_operation_catalog(contract_path)
    client = api_client or ApiClient(settings.api_base_url)
    tools = [*build_erp_tools(catalog, client), run_bi_text2sql]
    deep_agent_subagents = to_deep_agent_subagents(
        subagents,
        {"web_search": web_search},
    )
    return deepagents.create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        subagents=deep_agent_subagents,
        interrupt_on={"create_supplier": True},
        checkpointer=InMemorySaver(),
    )
