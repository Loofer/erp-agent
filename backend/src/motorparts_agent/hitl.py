"""Human-approval boundary for staged mutations."""

from typing import Any

from langgraph.types import interrupt

from .actions import PendingAction
from .api_client import ApiClient
from .openapi import Operation


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
    operation = Operation(action.operation_name, action.method, action.path)
    result = client.execute(
        operation,
        path_params={},
        query=action.query,
        body=action.body,
    )
    return {"status": "approved", "result": result}
