"""Reserved Text2SQL/BI boundary with no external dependencies."""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class BiText2SqlState(TypedDict):
    question: NotRequired[str]
    status: NotRequired[str]
    message: NotRequired[str]


def build_bi_text2sql_graph() -> CompiledStateGraph:
    """Return a placeholder graph that cannot connect to a database or LLM."""
    graph = StateGraph(BiText2SqlState)

    def not_configured(state: BiText2SqlState) -> dict[str, str]:
        return {
            "status": "not_configured",
            "message": "BI query is not configured.",
            "question": state.get("question", ""),
        }

    graph.add_node("not_configured", not_configured)
    graph.add_edge(START, "not_configured")
    graph.add_edge("not_configured", END)
    return graph.compile()
