"""Top-level route graph for the motor-parts agent."""

from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .config import load_settings
from .tools.api_client import ApiClient
from .tools.openapi import Operation, load_operation_catalog
from .workflows.bi_query import build_bi_query_graph
from .workflows.create import stage_supplier_creation
from .workflows.data_query import build_data_query_graph
from .workflows.research import research_placeholder

Route = Literal["data_query", "create", "research", "bi_query"]


class AgentState(TypedDict):
    route: Route
    operation_name: NotRequired[str]
    payload: NotRequired[dict[str, object]]
    question: NotRequired[str]
    status: NotRequired[str]
    message: NotRequired[str]
    error: NotRequired[str]
    api_result: NotRequired[dict[str, object]]
    pending_action: NotRequired[object]


def build_graph(
    catalog: dict[str, Operation], client: ApiClient
) -> CompiledStateGraph:
    """Route explicit caller intent to one isolated capability."""
    graph = StateGraph(AgentState)
    data_query = build_data_query_graph(catalog, client)
    bi_query = build_bi_query_graph()

    def run_data_query(state: AgentState) -> dict[str, object]:
        operation_name = state.get("operation_name", "getDashboard")
        result = data_query.invoke({"operation_name": operation_name})
        return {
            key: value
            for key, value in result.items()
            if key in {"api_result", "error"}
        }

    def run_create(state: AgentState) -> dict[str, object]:
        return {"pending_action": stage_supplier_creation(state.get("payload", {}), catalog)}

    def run_research(state: AgentState) -> dict[str, str]:
        return research_placeholder(state.get("question", ""))

    def run_bi_query(state: AgentState) -> dict[str, str]:
        result = bi_query.invoke({"question": state.get("question", "")})
        return {
            key: value
            for key, value in result.items()
            if key in {"status", "message"}
        }

    graph.add_node("data_query", run_data_query)
    graph.add_node("create", run_create)
    graph.add_node("research", run_research)
    graph.add_node("bi_query", run_bi_query)
    graph.add_conditional_edges(START, lambda state: state["route"])
    for route in ("data_query", "create", "research", "bi_query"):
        graph.add_edge(route, END)
    return graph.compile()


def build_default_graph() -> CompiledStateGraph:
    settings = load_settings()
    contract_path = Path(__file__).resolve().parents[2] / "openapi" / "swagger.json"
    catalog = load_operation_catalog(contract_path)
    return build_graph(catalog, ApiClient(settings.api_base_url))
