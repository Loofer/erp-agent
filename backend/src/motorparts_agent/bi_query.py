"""Reserved Text2SQL/BI boundary with no external dependencies."""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class BiQueryState(TypedDict):
    question: NotRequired[str]
    status: NotRequired[str]
    message: NotRequired[str]


def build_bi_query_graph() -> CompiledStateGraph:
    """Return a standalone placeholder that cannot connect to a DB or LLM."""
    graph = StateGraph(BiQueryState)

    def not_configured(state: BiQueryState) -> dict[str, str]:
        return {
            "status": "not_configured",
            "message": "BI query is not configured.",
            "question": state.get("question", ""),
        }

    graph.add_node("not_configured", not_configured)
    graph.add_edge(START, "not_configured")
    graph.add_edge("not_configured", END)
    return graph.compile()
