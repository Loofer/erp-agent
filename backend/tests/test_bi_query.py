from agent.workflows.bi_text2sql import build_bi_text2sql_graph


def test_bi_graph_reports_not_configured() -> None:
    result = build_bi_text2sql_graph().invoke({"question": "monthly purchasing trend"})

    assert result["status"] == "not_configured"
    assert result["question"] == "monthly purchasing trend"
