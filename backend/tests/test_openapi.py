from motorparts_agent.openapi import Operation


def test_catalog_classifies_dashboard_and_supplier_create(
    catalog: dict[str, Operation],
) -> None:
    assert catalog["getDashboard"].is_mutation is False
    assert catalog["getDashboard"].path == "/api/statistics/dashboard"
    assert catalog["create"].is_mutation is True
    assert catalog["create"].path == "/api/suppliers/create"
