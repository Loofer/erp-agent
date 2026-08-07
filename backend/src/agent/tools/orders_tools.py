"""Procurement-order tools for the motor-parts procurement agent."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def _create_order_request(
    client: ApiClient, order_payload: dict[str, Any]
) -> dict[str, object]:
    """Send an approved procurement order through the shared client."""
    return client.post("/api/orders/create", order_payload)


def _update_order_request(
    client: ApiClient, order_id: int, order_payload: dict[str, Any]
) -> dict[str, object]:
    """Send an approved procurement-order update through the shared client."""
    return client.put(f"/api/orders/update/{order_id}", order_payload)


def _erp_order_payload(order_payload: dict[str, Any]) -> dict[str, Any]:
    """Remove absent optional fields and preserve integer order quantities."""
    payload = _omit_none(order_payload)
    order_details = payload.get("orderDetail")
    if isinstance(order_details, list):
        for detail in order_details:
            if not isinstance(detail, dict):
                continue
            quantity = detail.get("quantity")
            if isinstance(quantity, float) and quantity.is_integer():
                detail["quantity"] = int(quantity)
    return payload


def _omit_none(value: Any) -> Any:
    """Copy JSON-like data while omitting keys whose value is None."""
    if isinstance(value, dict):
        return {
            key: _omit_none(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_omit_none(item) for item in value]
    return value


def _search_order_details_request(
    client: ApiClient,
    *,
    part_name: str | None,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, object]:
    """Search historical order details through the shared ERP client."""
    query = {
        key: value
        for key, value in {
            "partName": part_name,
            "startDate": start_date,
            "endDate": end_date,
        }.items()
        if value is not None
    }
    return client.get("/api/orders/search-details", query=query)


def build_order_tools(client: ApiClient) -> list[BaseTool]:
    """Build procurement-order tools for one configured API client."""

    @tool(parse_docstring=True)
    def create_order(order_payload: dict[str, Any]) -> dict[str, object]:
        """Create a procurement order after required human approval.

        Args:
            order_payload: Complete order payload. Each orderDetail item uses partId
                and must not include the read-only partDetail object.

        Returns:
            The ERP API response containing the created order.
        """
        payload = _erp_order_payload(order_payload)
        return _create_order_request(client, payload)

    @tool(parse_docstring=True)
    def update_order(
        order_id: int, order_payload: dict[str, Any]
    ) -> dict[str, object]:
        """Update a procurement order after required human approval.

        Args:
            order_id: ERP identifier of the procurement order to update.
            order_payload: Complete replacement payload. Each orderDetail item uses
                partId and must not include read-only fields.

        Returns:
            The ERP API response containing the updated order.
        """
        payload = _erp_order_payload(order_payload)
        return _update_order_request(client, order_id, payload)

    @tool(parse_docstring=True)
    def order_search_details(
        partName: str | None = None,
        startDate: str | None = None,
        endDate: str | None = None,
    ) -> dict[str, object]:
        """Search historical procurement-order details.

        Args:
            partName: Optional full or partial part name.
            startDate: Optional inclusive start date in yyyy-MM-dd format.
            endDate: Optional inclusive end date in yyyy-MM-dd format.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of order details. Each detail contains `id`, `orderId`,
            `partId`, `quantity`, `unitPrice`, `subtotal`, `remark`, `createTime`,
            `updateTime`, and `partDetail`. `partDetail` contains the part fields
            `id`, `partCode`, `name`, `model`, `specification`, `unit`,
            `purchasePrice`, `suggestedRetailPrice`, `stockWarningValue`,
            `supplierId`, `category`, `description`, `createTime`, `updateTime`,
            and `supplier`. The nested `supplier` contains `id`, `supplierCode`,
            `name`, `contactPerson`, `phone`, `email`, `address`, `creditRating`,
            and `status`.
        """
        return _search_order_details_request(
            client,
            part_name=partName,
            start_date=startDate,
            end_date=endDate,
        )

    return [create_order, update_order, order_search_details]
