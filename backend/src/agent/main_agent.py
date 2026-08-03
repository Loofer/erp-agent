"""Deep Agents runtime construction for the motor-parts agent."""

from pathlib import Path
import logging

import deepagents
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from .config import load_settings
from .memory.prompts import build_system_prompt
from .memory.runtime import (
    GLOBAL_SKILL_SOURCES,
    MEMORY_PATH,
    PERSISTENT_MEMORY_PATH,
    MemoryContext,
    build_agent_backend,
    build_runtime_permissions,
)
from .subagents.loader import (
    SubagentDefinition,
    load_subagent_definitions,
    to_deep_agent_subagents,
)
from .tools import build_parent_tools, build_subagent_only_tools
from .tools.bi_tools import run_bi_text2sql
from .tools.http_base import ApiClient
from .tools.openapi import load_operation_catalog
from .tools.research_tools import web_search


def create_main_agent(
        model: ChatOpenAI,
        *,
        subagents: tuple[SubagentDefinition, ...],
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
) -> CompiledStateGraph:
    """Build the primary Deep Agents runtime from declarative configuration."""
    settings = load_settings()
    contract_path = Path(__file__).resolve().parents[2] / "openapi" / "swagger.json"
    catalog = load_operation_catalog(contract_path)
    client = ApiClient(settings.api_base_url)

    parent_tools = [*build_parent_tools(catalog, client), run_bi_text2sql]

    subagent_tools = [*build_subagent_only_tools(catalog, client), web_search]

    tools_by_name = {
        tool.name: tool for tool in [*parent_tools, *subagent_tools]
    }

    deep_agent_subagents = to_deep_agent_subagents(subagents, tools_by_name)
    return deepagents.create_deep_agent(
        model=model,
        tools=parent_tools,
        system_prompt=build_system_prompt(),
        subagents=deep_agent_subagents,
        skills=GLOBAL_SKILL_SOURCES,
        memory=[MEMORY_PATH, PERSISTENT_MEMORY_PATH],
        backend=build_agent_backend(),
        debug=settings.debug,
        permissions=build_runtime_permissions(),
        checkpointer=checkpointer,
        store=store,
        context_schema=MemoryContext,
    )


def load_agent_graph(
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
) -> CompiledStateGraph:
    """Load YAML subagents and build the deployment graph."""
    settings = load_settings()
    model = ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,

    )

    config_directory = Path(__file__).parent / "subagents" / "configs"
    subagents = load_subagent_definitions(config_directory)
    return create_main_agent(
        model,
        subagents=subagents,
        checkpointer=checkpointer,
        store=store,
    )
