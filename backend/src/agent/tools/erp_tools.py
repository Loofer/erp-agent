"""The intentionally small set of ordinary in-process ERP tools."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from .api_client import CATALOGED_SUPPLIER_CREATE, ApiClient
from .openapi import Operation

ACTIVE_READ_OPERATION = "getDashboard"
SUPPLIER_CREATE_OPERATION = "create"


def build_erp_tools(
    catalog: dict[str, Operation], client: ApiClient
) -> list[BaseTool]:
    """Bind the allowed ERP operations to the configured API client."""
    dashboard_operation = catalog[ACTIVE_READ_OPERATION]
    supplier_operation = catalog[SUPPLIER_CREATE_OPERATION]
    if supplier_operation != CATALOGED_SUPPLIER_CREATE:
        raise ValueError("Supplier creation must use the cataloged create operation.")

    @tool
    def get_dashboard() -> dict[str, object]:
        """Fetch the procurement dashboard."""
        return client.execute(
            dashboard_operation,
            path_params={},
            query={},
            body=None,
        )

    @tool
    def create_supplier(payload: dict[str, Any]) -> dict[str, object]:
        """Create a supplier after Deep Agents' required human approval."""
        return client._send_supplier_create(dict(payload))

    return [get_dashboard, create_supplier]
