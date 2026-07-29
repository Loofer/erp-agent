import json

from agent.middlewares.hitl import execute_after_approval
from agent.schema import PendingAction
from agent.tools.erp_tools import stage_create_supplier


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


def test_approved_non_supplier_action_does_not_send_request(client, requests) -> None:
    action = PendingAction(
        "create_1",
        "POST",
        "/api/parts/create",
        {},
        {"partCode": "P-001", "name": "Brake Pad"},
    )

    assert execute_after_approval(action, True, client) == {"status": "rejected"}
    assert requests == []


def test_staged_supplier_payload_is_isolated_from_the_source_dict(
    catalog, client, requests
) -> None:
    payload = {
        "supplierCode": "S-001",
        "name": "Acme Parts",
        "contact": {"name": "Jane"},
    }
    action = stage_create_supplier(payload, catalog)

    payload["name"] = "Changed Supplier"
    payload["contact"]["name"] = "Changed Contact"

    assert action.body == {
        "supplierCode": "S-001",
        "name": "Acme Parts",
        "contact": {"name": "Jane"},
    }
    execute_after_approval(action, True, client)
    assert json.loads(requests[0].content) == action.body
