"""Application lifecycle loader for the configured agent graph."""

from langgraph.graph.state import CompiledStateGraph

from agent.main_agent import build_default_graph


def load_agent_graph() -> CompiledStateGraph:
    """Build the graph once application startup requires it."""
    return build_default_graph()
