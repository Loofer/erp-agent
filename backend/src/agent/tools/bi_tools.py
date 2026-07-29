"""Adapter that exposes the BI placeholder as an ordinary Deep Agents tool."""

from langchain_core.tools import tool

from ..workflows.bi_text2sql import build_bi_text2sql_graph


@tool
def run_bi_text2sql(question: str) -> dict[str, str]:
    """Run the reserved Text2SQL/BI workflow for a procurement question."""
    return build_bi_text2sql_graph().invoke({"question": question})
