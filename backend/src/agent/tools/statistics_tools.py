"""Statistics-domain tools backed by reviewed Swagger operations."""

from langchain_core.tools import BaseTool, tool

from .http_base import ApiClient
from .openapi import Operation

ACTIVE_READ_OPERATION = "getDashboard"


def build_statistics_tools(
    catalog: dict[str, Operation], client: ApiClient
) -> list[BaseTool]:
    """Bind the approved procurement-dashboard read operation."""
    dashboard_operation = catalog[ACTIVE_READ_OPERATION]

    @tool
    def get_dashboard() -> dict[str, object]:
        """Fetch the procurement dashboard."""
        return client.execute(
            dashboard_operation,
            path_params={},
            query={},
            body=None,
        )

    return [get_dashboard]
