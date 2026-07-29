from typing import Any

from agent.tools import bi_tools


def test_bi_adapter_invokes_placeholder_graph_without_external_dependencies(
    monkeypatch: Any,
) -> None:
    observed: dict[str, object] = {}

    class PlaceholderGraph:
        def invoke(self, state: dict[str, str]) -> dict[str, str]:
            observed["state"] = state
            return {
                "status": "not_configured",
                "question": state["question"],
                "message": "BI query is not configured.",
            }

    monkeypatch.setattr(
        bi_tools, "build_bi_text2sql_graph", lambda: PlaceholderGraph()
    )

    result = bi_tools.run_bi_text2sql.invoke({"question": "monthly purchasing trend"})

    assert observed == {"state": {"question": "monthly purchasing trend"}}
    assert result == {
        "status": "not_configured",
        "question": "monthly purchasing trend",
        "message": "BI query is not configured.",
    }
