"""Parts-domain tools for procurement analysis."""

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def _search_parts_request(client: ApiClient, name: str) -> dict[str, object]:
    """Search parts by name through the shared ERP client."""
    return client.get("/api/parts/search", query={"name": name})


def _parts_by_supplier_request(
    client: ApiClient, supplier_id: int
) -> dict[str, object]:
    """Fetch the parts associated with one supplier through the shared client."""
    return client.get(f"/api/parts/supplier/{supplier_id}")


def build_part_tools(client: ApiClient) -> list[BaseTool]:
    """Build read-only parts tools for one configured API client."""

    @tool(parse_docstring=True)
    def part_query(name: str) -> dict[str, object]:
        """Search parts by full or partial name.

        Args:
            name: Full or partial part name to search for.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of parts. Each part contains `id`, `partCode`, `name`,
            `model`, `specification`, `unit`, `purchasePrice`,
            `suggestedRetailPrice`, `stockWarningValue`, `supplierId`, `category`,
            `description`, `deleted`, `createTime`, and `updateTime`.
        """
        return _search_parts_request(client, name)

    @tool(parse_docstring=True)
    def part_search(name: str) -> dict[str, object]:
        """Search parts by full or partial name.

        Args:
            name: Full or partial part name to search for.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is a list of parts. Each part contains `id`, `partCode`, `name`,
            `model`, `specification`, `unit`, `purchasePrice`,
            `suggestedRetailPrice`, `stockWarningValue`, `supplierId`, `category`,
            `description`, `deleted`, `createTime`, and `updateTime`.
        """
        return _search_parts_request(client, name)

    @tool(parse_docstring=True)
    def part_by_supplier(supplier_id: int) -> dict[str, object]:
        """List all parts provided by an ERP supplier.

        Args:
            supplier_id: ERP identifier of the supplier.

        Returns:
            ERP response wrapper with `code` (business status code), `message`
            (status text), `timestamp` (response epoch milliseconds), and `data`.
            `data` is the supplier's list of parts. Each part contains `id`,
            `partCode`, `name`, `model`, `specification`, `unit`, `purchasePrice`,
            `suggestedRetailPrice`, `stockWarningValue`, `supplierId`, `category`,
            `description`, `deleted`, `createTime`, and `updateTime`.
        """
        return _parts_by_supplier_request(client, supplier_id)

    return [part_query, part_search, part_by_supplier]
