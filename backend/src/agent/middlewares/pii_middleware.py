"""PII guardrails with a narrow exception for business workflow inputs."""

from __future__ import annotations

import re
from typing import Any

from langchain.agents.middleware import PIIMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

_BUSINESS_WORKFLOW_PATTERN = re.compile(
    r"(?:"
    r"供应商|采购(?:订单|单)?|订单|联系人|"
    r"supplier(?:_draft|Code|_info)?|contactPerson|"
    r"request_supplier_info|request_order_info|"
    r"create_supplier|create_order|update_order|"
    r"order(?:_draft|Number|_info)?"
    r")",
    re.IGNORECASE,
)


class BusinessWorkflowPIIMiddleware(PIIMiddleware):
    """Keep contact fields intact while a supplier or order workflow is running.

    LangChain's built-in :class:`PIIMiddleware` redacts the whole latest user
    message before the model chooses a tool.  For supplier/order workflows,
    that would make a real phone number or email unrecoverable before the
    model can call ``request_*_info`` or the approved write tools.

    This deliberately narrow exception applies only to the two business PII
    types configured below and only when the latest input names a supplier or
    procurement-order workflow.  Output-side redaction remains enabled, so
    streamed text and tool-call display data do not expose those values.
    """

    def before_model(
        self,
        state: dict[str, Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        if _contains_business_workflow_input(state.get("messages", [])):
            return None
        return super().before_model(state, runtime)


def _contains_business_workflow_input(messages: object) -> bool:
    """Return whether the newest human message belongs to a protected workflow."""
    if not isinstance(messages, list):
        return False
    business_tools = {
        "request_supplier_info",
        "request_order_info",
        "create_supplier",
        "create_order",
        "update_order",
    }
    for message in messages:
        if isinstance(message, ToolMessage) and message.name in business_tools:
            return True
        if isinstance(message, AIMessage) and any(
            call.get("name") in business_tools
            for call in message.tool_calls
            if isinstance(call, dict)
        ):
            return True
    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue
        content = message.content
        return isinstance(content, str) and bool(_BUSINESS_WORKFLOW_PATTERN.search(content))
    return False

tool_call_limit_middleware = ToolCallLimitMiddleware(
    thread_limit=15,
    run_limit=8,
)

email_pii_middleware = BusinessWorkflowPIIMiddleware(
    "email",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=True,
    apply_to_tool_results=True,
)

credit_card_pii_middleware = PIIMiddleware(
    "credit_card",
    strategy="mask",
    apply_to_input=True,
)

api_key_pii_middleware = PIIMiddleware(
    "api_key",
    detector=r"sk-[a-zA-Z0-9]{32}",
    strategy="block",
    apply_to_input=True,
)

phone_number_pii_middleware = BusinessWorkflowPIIMiddleware(
    pii_type="phone_number",
    detector=r"1[3-9]\d{9}",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=True,
    apply_to_tool_results=True,
)

id_card_pii_middleware = PIIMiddleware(
    pii_type="id_card",
    detector=r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=False,
    apply_to_tool_results=False,
)
