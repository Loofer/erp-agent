from motorparts_agent.graph import build_graph


def test_top_level_graph_exposes_all_required_routes(catalog, client) -> None:
    graph = build_graph(catalog, client)

    assert graph.invoke({"route": "bi_query", "question": "trend"})["status"] == "not_configured"
