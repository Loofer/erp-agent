"""Statistics-domain tools backed by the ERP HTTP API."""

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient


def build_statistics_tools(client: ApiClient) -> list[BaseTool]:
    """Bind the procurement-dashboard read endpoint."""

    @tool
    def get_dashboard() -> dict[str, object]:
        """Fetch the procurement dashboard."""
        return client.get("/api/statistics/dashboard")

    return [get_dashboard]
