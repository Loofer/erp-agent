from motorparts_agent.bi_query import build_bi_query_graph


def test_bi_graph_reports_not_configured() -> None:
    result = build_bi_query_graph().invoke({"question": "monthly purchasing trend"})

    assert result["status"] == "not_configured"
    assert result["question"] == "monthly purchasing trend"
