from agent.tools import build_parent_tools, build_subagent_only_tools
from agent.tools.customers_tools import build_customer_tools
from agent.tools.inventory_tools import build_inventory_tools
from agent.tools.logistics_tools import build_logistics_tools
from agent.tools.orders_tools import build_order_tools
from agent.tools.parts_tools import build_part_tools
from agent.tools.suppliers_tools import build_supplier_tools


def test_parent_tools_are_limited_to_read_only_domain_operations(
    catalog: object, client: object
) -> None:
    tools = build_parent_tools(catalog, client)

    assert [tool.name for tool in tools] == ["get_dashboard"]


def test_subagent_only_tools_are_not_registered_on_the_parent(
    catalog: object, client: object
) -> None:
    tools = build_subagent_only_tools(catalog, client)

    assert [tool.name for tool in tools] == [
        "create_supplier",
        "request_order_info",
    ]


def test_future_domain_modules_expose_no_tools_yet() -> None:
    assert build_part_tools() == []
    assert build_order_tools() == []
    assert build_inventory_tools() == []
    assert build_logistics_tools() == []
    assert build_customer_tools() == []


def test_supplier_tool_exposes_a_parseable_payload_contract(
    catalog: object, client: object
) -> None:
    supplier_tool = build_supplier_tools(catalog, client)[0]

    schema = supplier_tool.args_schema.model_json_schema()

    assert schema["properties"]["payload"]["description"] == (
        "Supplier data accepted by the reviewed supplier creation operation."
    )
