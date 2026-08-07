"""Inventory-domain tools for procurement analysis."""

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def _inventory_warning_request(client: ApiClient) -> dict[str, object]:
    """Fetch low-stock inventory warnings through the shared ERP client."""
    return client.get("/api/inventory/warning")


def build_inventory_tools(client: ApiClient) -> list[BaseTool]:
    """Build read-only inventory tools for one configured API client."""

    @tool(parse_docstring=True)
    def inventory_warning() -> dict[str, object]:
        """List inventory records at or below their safety-stock threshold.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of warning records. Each record contains `id`,
            `partId`, `currentQuantity`, `safetyStock`, `lastInboundTime`,
            `lastOutboundTime`, `warehouseLocation`, `deleted`, `createTime`,
            `updateTime`, and `partDetail`. `partDetail` contains `id`,
            `partCode`, `name`, `model`, `specification`, `unit`, `purchasePrice`,
            `suggestedRetailPrice`, `stockWarningValue`, `supplierId`, `category`,
            `description`, `deleted`, `createTime`, and `updateTime`.
        """
        return _inventory_warning_request(client)

    return [inventory_warning]
