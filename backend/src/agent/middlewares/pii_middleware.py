from langchain.agents.middleware import ToolCallLimitMiddleware, PIIMiddleware

from agent.middlewares import RequestContextPromptMiddleware

tool_call_limit_middleware = ToolCallLimitMiddleware(
    thread_limit=15,
    run_limit=8,
)

email_pii_middleware = PIIMiddleware(
    "email",
    strategy="redact",
    apply_to_input=True,
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

phone_number_pii_middleware = PIIMiddleware(
    pii_type="phone_number",
    detector=r"1[3-9]\d{9}",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=False,
    apply_to_tool_results=False
)

id_card_pii_middleware = PIIMiddleware(
    pii_type="id_card",
    detector=r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=False,
    apply_to_tool_results=False
)