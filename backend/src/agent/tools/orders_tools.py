"""Procurement-order tools for the motor-parts procurement agent."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def _create_order_request(
    client: ApiClient, order: dict[str, Any]
) -> dict[str, object]:
    """Send an approved procurement order through the shared client."""
    return client.post("/api/orders/create", dict(order))


def _update_order_request(
    client: ApiClient, order_id: int, order: dict[str, Any]
) -> dict[str, object]:
    """Send an approved procurement-order update through the shared client."""
    return client.put(f"/api/orders/update/{order_id}", dict(order))


def build_order_tools(client: ApiClient) -> list[BaseTool]:
    """Build procurement-order tools for one configured API client."""

    @tool(parse_docstring=True)
    def create_order(order: dict[str, Any]) -> dict[str, object]:
        """Create a procurement order after required human approval.

        Args:
            order: Complete order payload, including orderDetail line items and
                each line item's partDetail when available.

        Returns:
            The ERP API response containing the created order.
        """
        return _create_order_request(client, order)

    @tool(parse_docstring=True)
    def update_order(order_id: int, order: dict[str, Any]) -> dict[str, object]:
        """Update a procurement order after required human approval.

        Args:
            order_id: ERP identifier of the procurement order to update.
            order: Complete replacement payload, including orderDetail line items
                and each line item's partDetail when available.

        Returns:
            The ERP API response containing the updated order.
        """
        return _update_order_request(client, order_id, order)

    return [create_order, update_order]
