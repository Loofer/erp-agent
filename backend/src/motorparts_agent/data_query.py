"""Read-only data-query subgraph."""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .api_client import ApiClient
from .openapi import Operation


class QueryState(TypedDict):
    operation_name: str
    path_params: NotRequired[dict[str, object]]
    query: NotRequired[dict[str, object]]
    api_result: NotRequired[dict[str, object]]
    error: NotRequired[str]


def build_data_query_graph(
    catalog: dict[str, Operation], client: ApiClient | None = None
) -> CompiledStateGraph:
    """Build a graph that categorically rejects every mutation."""
    graph = StateGraph(QueryState)

    def execute_query(state: QueryState) -> dict[str, object]:
        operation = catalog[state["operation_name"]]
        if operation.is_mutation:
            return {"error": "Mutation operations are not available in data_query."}
        if operation.name != "getDashboard":
            return {"error": "This read operation is not active in data_query."}
        if client is None:
            return {"error": "No API client is configured."}
        return {
            "api_result": client.execute(
                operation,
                path_params=state.get("path_params", {}),
                query=state.get("query", {}),
                body=None,
            )
        }

    graph.add_node("execute_query", execute_query)
    graph.add_edge(START, "execute_query")
    graph.add_edge("execute_query", END)
    return graph.compile()
