"""Human-input tools used by declarative workflow subagents."""

from typing import Any

from langchain_core.tools import BaseTool, tool


@tool(parse_docstring=True)
def request_order_info(
    order_draft: dict[str, Any], missing_fields: list[str]
) -> dict[str, object]:
    """Request human completion of missing procurement-order data.

    The native Deep Agents approval middleware pauses this tool call. An
    approver can edit ``order_draft`` before approval to supply missing values.

    Args:
        order_draft: Current order data, including fields that still need review.
        missing_fields: Required order fields that need human confirmation.

    Returns:
        The reviewed order draft and its requested missing fields.
    """
    return {
        "status": "human_input_requested",
        "order_draft": dict(order_draft),
        "missing_fields": list(missing_fields),
    }


def build_hitl_tools() -> list[BaseTool]:
    """Return normal tools whose calls require native human intervention."""
    return [request_order_info]
