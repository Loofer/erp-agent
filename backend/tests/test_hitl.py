import json

from motorparts_agent.actions import PendingAction
from motorparts_agent.hitl import execute_after_approval


def test_rejected_action_does_not_send_request(client, requests) -> None:
    action = PendingAction(
        "create",
        "POST",
        "/api/suppliers/create",
        {},
        {"supplierCode": "S-001", "name": "Acme Parts"},
    )

    assert execute_after_approval(action, False, client) == {"status": "rejected"}
    assert requests == []


def test_approved_action_sends_exactly_the_staged_request(client, requests) -> None:
    action = PendingAction(
        "create",
        "POST",
        "/api/suppliers/create",
        {"source": "agent"},
        {"supplierCode": "S-001", "name": "Acme Parts"},
    )

    result = execute_after_approval(action, True, client)

    assert result["status"] == "approved"
    assert [(request.method, request.url.path, dict(request.url.params)) for request in requests] == [
        ("POST", "/api/suppliers/create", {"source": "agent"})
    ]
    assert json.loads(requests[0].content) == {
        "supplierCode": "S-001",
        "name": "Acme Parts",
    }
