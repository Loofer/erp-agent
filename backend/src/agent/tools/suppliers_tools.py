"""Supplier-domain tools for the motor-parts procurement agent.

This module exposes reviewed supplier actions as ordinary LangChain tools while
keeping the Swagger-aware HTTP client behind the tool boundary.
"""

from typing import Any

from langchain_core.tools import BaseTool, tool

from .http_base import CATALOGED_SUPPLIER_CREATE, ApiClient
from .openapi import Operation

SUPPLIER_CREATE_OPERATION = "create"


def _create_supplier_request(
    client: ApiClient, payload: dict[str, Any]
) -> dict[str, object]:
    """Send the approved supplier creation request through the shared client."""
    return client._send_supplier_create(dict(payload))


def build_supplier_tools(
    catalog: dict[str, Operation], client: ApiClient
) -> list[BaseTool]:
    """Build the reviewed supplier-domain tools for one configured API client."""
    supplier_operation = catalog[SUPPLIER_CREATE_OPERATION]
    if supplier_operation != CATALOGED_SUPPLIER_CREATE:
        raise ValueError("Supplier creation must use the cataloged create operation.")

    @tool(parse_docstring=True)
    def create_supplier(payload: dict[str, Any]) -> dict[str, object]:
        """Create a supplier after Deep Agents' required human approval.

        Args:
            payload: Supplier data accepted by the reviewed supplier creation operation.

        Returns:
            The API response for the approved supplier creation request.
        """
        return _create_supplier_request(client, payload)

    return [create_supplier]
