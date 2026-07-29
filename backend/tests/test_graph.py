from agent.main_agent import build_graph


def test_top_level_graph_exposes_all_required_routes(catalog, client) -> None:
    graph = build_graph(catalog, client)

    data_query = graph.invoke({"route": "data_query", "operation_name": "getDashboard"})
    create = graph.invoke(
        {
            "route": "create",
            "payload": {"supplierCode": "S-001", "name": "Acme Parts"},
        }
    )
    research = graph.invoke({"route": "research", "question": "supplier trends"})
    bi_query = graph.invoke({"route": "bi_query", "question": "purchasing trend"})

    assert data_query["api_result"] == {"code": 200, "data": {"ok": True}}
    assert create["pending_action"].operation_name == "create"
    assert create["pending_action"].method == "POST"
    assert create["pending_action"].path == "/api/suppliers/create"
    assert create["pending_action"].body == {
        "supplierCode": "S-001",
        "name": "Acme Parts",
    }
    assert research["status"] == "not_configured"
    assert bi_query["status"] == "not_configured"
