from motorparts_agent.data_query import build_data_query_graph
from motorparts_agent.openapi import Operation


def test_query_graph_rejects_supplier_create(catalog: dict[str, Operation]) -> None:
    result = build_data_query_graph(catalog).invoke({"operation_name": "create"})

    assert result["error"] == "Mutation operations are not available in data_query."
