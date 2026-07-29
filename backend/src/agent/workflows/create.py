"""Focused supplier-creation workflow boundary."""

from ..schema import PendingAction
from ..tools.erp_tools import stage_create_supplier
from ..tools.openapi import Operation


def stage_supplier_creation(
    payload: dict[str, object], catalog: dict[str, Operation]
) -> PendingAction:
    """Stage the sole active create action without network I/O."""
    return stage_create_supplier(payload, catalog)
