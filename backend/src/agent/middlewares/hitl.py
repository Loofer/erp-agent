"""Human-approval boundary for staged mutations."""

from typing import Any

from langgraph.types import interrupt

from ..schema import PendingAction
from ..tools.api_client import CATALOGED_SUPPLIER_CREATE, ApiClient


def approval_payload(action: PendingAction) -> dict[str, object]:
    return {
        "operation_name": action.operation_name,
        "method": action.method,
        "path": action.path,
        "query": action.query,
        "body": action.body,
    }


def request_approval(action: PendingAction) -> Any:
    """Interrupt a LangGraph run until a human supplies an approval decision."""
    return interrupt(approval_payload(action))


def execute_after_approval(
    action: PendingAction, approved: bool, client: ApiClient
) -> dict[str, object]:
    """Execute exactly one staged action only after an affirmative decision."""
    if not approved:
        return {"status": "rejected"}
    if not _is_cataloged_supplier_create(action):
        return {"status": "rejected"}
    result = client._send_approved_supplier_create(action)
    return {"status": "approved", "result": result}


def _is_cataloged_supplier_create(action: PendingAction) -> bool:
    return (
        action.operation_name == CATALOGED_SUPPLIER_CREATE.name
        and action.method == CATALOGED_SUPPLIER_CREATE.method
        and action.path == CATALOGED_SUPPLIER_CREATE.path
    )
