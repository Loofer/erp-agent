"""Supplier-domain tools for the motor-parts procurement agent."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def _create_supplier_request(
    client: ApiClient, supplier_payload: dict[str, Any]
) -> dict[str, object]:
    """Send the approved supplier creation request through the shared client."""
    return client.post("/api/suppliers/create", supplier_payload)


def _erp_supplier_payload(supplier_payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only API-writable supplier fields and omit absent optional values."""
    writable_fields = (
        "supplierCode",
        "name",
        "contactPerson",
        "phone",
        "email",
        "address",
        "creditRating",
    )
    return {
        field: value
        for field, value in supplier_payload.items()
        if field in writable_fields and value not in (None, "")
    }


def _search_suppliers_request(client: ApiClient, name: str) -> dict[str, object]:
    """Search suppliers by name through the shared client."""
    return client.get("/api/suppliers/search", query={"name": name})


def build_supplier_tools(client: ApiClient) -> list[BaseTool]:
    """Build supplier-domain tools for one configured API client."""

    @tool(parse_docstring=True)
    def create_supplier(supplier_payload: dict[str, Any]) -> dict[str, object]:
        """Create a supplier after Deep Agents' required human approval.

        Args:
            supplier_payload: Validated supplier data. It may include only
                supplierCode, name, contactPerson, phone, email, address, and
                creditRating. ERP-managed fields such as status are ignored.

        Returns:
            The API response for the approved supplier creation request.
        """
        payload = _erp_supplier_payload(supplier_payload)
        return _create_supplier_request(client, payload)

    @tool(parse_docstring=True)
    def search_suppliers(name: str) -> dict[str, object]:
        """Search suppliers whose names match the supplied text.

        Args:
            name: Full or partial supplier name to search for.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of matching suppliers. Each supplier contains `id`,
            `supplierCode`, `name`, `contactPerson`, `phone`, `email`, `address`,
            `creditRating`, `status`, `deleted`, `createTime`, and `updateTime`.
        """
        return _search_suppliers_request(client, name)

    @tool(parse_docstring=True)
    def supplier_query(name: str) -> dict[str, object]:
        """Find supplier records by full or partial name for procurement analysis.

        Args:
            name: Full or partial supplier name to search for.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of matching suppliers. Each supplier contains `id`,
            `supplierCode`, `name`, `contactPerson`, `phone`, `email`, `address`,
            `creditRating`, `status`, `deleted`, `createTime`, and `updateTime`.
        """
        return _search_suppliers_request(client, name)

    return [create_supplier, search_suppliers, supplier_query]
