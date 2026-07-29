"""The intentionally small set of direct in-process ERP tools."""

from ..schema import PendingAction
from .api_client import CATALOGED_SUPPLIER_CREATE, ApiClient
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
    if operation != CATALOGED_SUPPLIER_CREATE:
        raise ValueError("Supplier creation must use the cataloged create operation.")
    return PendingAction(operation.name, operation.method, operation.path, {}, payload)
