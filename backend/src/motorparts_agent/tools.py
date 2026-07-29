"""The intentionally small set of active agent tools."""

from .actions import PendingAction
from .api_client import ApiClient
from .openapi import Operation

ACTIVE_READ_OPERATION = "getDashboard"
SUPPLIER_CREATE_OPERATION = "create"


def get_dashboard(catalog: dict[str, Operation], client: ApiClient) -> dict[str, object]:
    """Execute the sole active read tool."""
    operation = catalog[ACTIVE_READ_OPERATION]
    return client.execute(operation, path_params={}, query={}, body=None)


def stage_create_supplier(
    payload: dict[str, object], catalog: dict[str, Operation]
) -> PendingAction:
    """Prepare supplier creation without performing network I/O."""
    operation = catalog[SUPPLIER_CREATE_OPERATION]
    if not operation.is_mutation:
        raise ValueError("Supplier creation operation must be a mutation.")
    return PendingAction(operation.name, operation.method, operation.path, {}, payload)
