"""Human-input tools used by declarative workflow subagents."""

from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt


@tool(parse_docstring=True)
def request_order_info(
    order_draft: dict[str, Any], missing_fields: list[str], message: str = ""
) -> dict[str, object]:
    """Request human input for fields identified by the order-management skill.

    Args:
        order_draft: Current procurement-order draft to retain while awaiting input.
        missing_fields: Field paths the agent determined are missing or invalid.
        message: User-facing question generated from the order-management skill.

    Returns:
        The complete draft without an interrupt, or the requested fields and the
        user's free-text response.
    """
    if not missing_fields:
        return {
            "status": "complete",
            "order_draft": dict(order_draft),
            "missing_fields": [],
        }

    human_response = interrupt(
        {
            "kind": "tool_input",
            "tool_name": "request_order_info",
            "message": message,
            "order_draft": dict(order_draft),
            "missing_fields": list(missing_fields),
        }
    )
    return {
        "status": "human_input_received",
        "order_draft": dict(order_draft),
        "missing_fields": list(missing_fields),
        "human_response": human_response,
    }


@tool(parse_docstring=True)
def request_supplier_info(
    supplier_draft: dict[str, Any], missing_fields: list[str]
) -> dict[str, object]:
    """Request human completion of missing supplier data.

    Args:
        supplier_draft: Current supplier data, including fields that still need review.
        missing_fields: Required supplier fields that need human confirmation.

    Returns:
        The current supplier draft and its requested missing fields.
    """
    return {
        "status": "human_input_requested",
        "supplier_draft": dict(supplier_draft),
        "missing_fields": list(missing_fields),
    }


def build_hitl_tools() -> list[BaseTool]:
    """Return tools that collect input through native human intervention."""
    return [request_order_info, request_supplier_info]
