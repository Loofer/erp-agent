"""Deep Agents runtime construction for the motor-parts agent."""

import asyncio
from pathlib import Path

import deepagents
from backend.configs.settings import load_settings
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from .memory.prompts import build_system_prompt
from .memory.runtime import (
    MemoryContext,
    build_agent_backend,
    build_runtime_permissions,
)
from .middlewares import RequestContextPromptMiddleware
from .middlewares.pii_middleware import (
    api_key_pii_middleware,
    credit_card_pii_middleware,
    email_pii_middleware,
    id_card_pii_middleware,
    phone_number_pii_middleware,
    tool_call_limit_middleware,
)
from .middlewares.prompt_injection_middleware import PromptInjectionMiddleware
from .rag.hybrid_retriever import HybridRetriever
from .rag.runtime import build_hybrid_retriever
from .subagents.loader import (
    SubagentDefinition,
    load_subagent_definitions,
    to_deep_agent_subagents,
)
from .tools import build_subagent_only_tools
from .tools.http_base import ApiClient
from .tools.knowledge_tools import build_knowledge_tools


def create_main_agent(
        model: ChatOpenAI,
        *,
        subagents: tuple[SubagentDefinition, ...],
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        rag_retriever: HybridRetriever | None = None,
) -> CompiledStateGraph:
    """Build the primary Deep Agents runtime from declarative configuration."""
    return _create_main_agent(
        model,
        subagents=subagents,
        checkpointer=checkpointer,
        store=store,
        rag_retriever=rag_retriever,
    )


def _create_main_agent(
        model: ChatOpenAI,
        *,
        subagents: tuple[SubagentDefinition, ...],
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        rag_retriever: HybridRetriever | None = None,
        api_client: ApiClient | None = None,
) -> CompiledStateGraph:
    """Build the graph with optional dependency injection for offline evaluation."""
    settings = load_settings()
    if api_client is None:
        api_token = (
            settings.motorparts_api_token.get_secret_value()
            if settings.motorparts_api_token
            else None
        )
        api_client = ApiClient(
            settings.motorparts_api_base_url,
            api_token=api_token,
        )

    parent_tools = build_knowledge_tools(rag_retriever)

    subagent_tools = build_subagent_only_tools(api_client)

    tools_by_name = {
        tool.name: tool for tool in [*parent_tools, *subagent_tools]
    }

    backend_root = Path(__file__).resolve().parents[2]
    runtime_permissions = build_runtime_permissions()
    deep_agent_subagents = to_deep_agent_subagents(
        subagents,
        tools_by_name,
        backend_root=backend_root,
    )
    return deepagents.create_deep_agent(
        model=model,
        name="erp-agent",
        tools=parent_tools,
        system_prompt=build_system_prompt(),
        subagents=deep_agent_subagents,
        skills=["/skills/main/"],
        memory=["/memory/AGENTS.md", "/memories/preferences.md"],
        backend=build_agent_backend(store=store),
        debug=settings.debug,
        permissions=runtime_permissions,
        checkpointer=checkpointer,
        store=store,
        middleware=[
            PromptInjectionMiddleware(),
            RequestContextPromptMiddleware(),
            tool_call_limit_middleware,
            email_pii_middleware,
            credit_card_pii_middleware,
            api_key_pii_middleware,
            phone_number_pii_middleware,
            id_card_pii_middleware,
        ],
        context_schema=MemoryContext,
    )


def load_agent_graph(
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        rag_retriever: HybridRetriever | None = None,
        api_client: ApiClient | None = None,
        model_name: str | None = None,
) -> CompiledStateGraph:
    """Load YAML subagents and build the deployment graph."""
    settings = load_settings()
    if rag_retriever is None:
        try:
            rag_retriever = build_hybrid_retriever(settings)
        except Exception:  # noqa: BLE001
            rag_retriever = None
    model = ChatOpenAI(
        model=model_name or settings.motorparts_agent_model,
        api_key=settings.motorparts_model_api_key,
        base_url=settings.motorparts_model_base_url,
        max_tokens=105000,
    )

    config_directory = Path(__file__).parent / "subagents" / "configs"
    subagents = load_subagent_definitions(config_directory)
    if api_client is None:
        return create_main_agent(
            model,
            subagents=subagents,
            checkpointer=checkpointer,
            store=store,
            rag_retriever=rag_retriever,
        )
    return _create_main_agent(
        model,
        subagents=subagents,
        checkpointer=checkpointer,
        store=store,
        rag_retriever=rag_retriever,
        api_client=api_client,
    )


def load_langgraph_dev_agent_graph() -> CompiledStateGraph:
    """Build the graph for ``langgraph dev`` managed persistence."""
    return load_agent_graph()


async def load_langgraph_dev_agent_graph_async() -> CompiledStateGraph:
    """Build the development graph without blocking LangGraph's event loop."""
    return await asyncio.to_thread(load_agent_graph)
