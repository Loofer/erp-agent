import pytest
from langchain.agents.middleware import PIIDetectionError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.middlewares.pii_middleware import (
    api_key_pii_middleware,
    credit_card_pii_middleware,
    email_pii_middleware,
    phone_number_pii_middleware,
)


def _latest_content(result: dict | None, original: HumanMessage) -> str:
    messages = result["messages"] if result is not None else [original]
    return str(messages[-1].content)


def test_business_supplier_input_preserves_phone_and_email_for_tools() -> None:
    message = HumanMessage(
        content=(
            '创建供应商 supplier_draft={"phone":"13800138000",'
            '"email":"buyer@example.com"}'
        )
    )
    state = {"messages": [message]}

    assert email_pii_middleware.before_model(state, None) is None
    assert phone_number_pii_middleware.before_model(state, None) is None


def test_business_order_input_preserves_phone_and_email_for_tools() -> None:
    message = HumanMessage(
        content="采购订单联系人电话 13800138000，邮箱 buyer@example.com"
    )
    state = {"messages": [message]}

    assert email_pii_middleware.before_model(state, None) is None
    assert phone_number_pii_middleware.before_model(state, None) is None


def test_business_follow_up_without_keywords_keeps_contact_fields() -> None:
    state = {
        "messages": [
            HumanMessage(content="创建供应商 测试供应商"),
            ToolMessage(
                content="请补充联系电话和邮箱",
                name="request_supplier_info",
                tool_call_id="call-1",
            ),
            HumanMessage(content="13800138000 buyer@example.com"),
        ]
    }

    assert email_pii_middleware.before_model(state, None) is None
    assert phone_number_pii_middleware.before_model(state, None) is None


def test_regular_chat_input_still_redacts_email_and_phone() -> None:
    email_message = HumanMessage(content="请记住我的邮箱 buyer@example.com")
    phone_message = HumanMessage(content="请记住我的手机号 13800138000")

    assert "[REDACTED_EMAIL]" in _latest_content(
        email_pii_middleware.before_model({"messages": [email_message]}, None),
        email_message,
    )
    assert "[REDACTED_PHONE_NUMBER]" in _latest_content(
        phone_number_pii_middleware.before_model({"messages": [phone_message]}, None),
        phone_message,
    )


def test_business_workflow_keeps_high_risk_pii_guardrails() -> None:
    credit_card = HumanMessage(content="创建供应商，卡号 4111-1111-1111-1111")
    api_key = HumanMessage(content="创建供应商，密钥 sk-12345678901234567890123456789012")

    card_result = credit_card_pii_middleware.before_model(
        {"messages": [credit_card]}, None
    )
    assert "****-****-****-1111" in _latest_content(card_result, credit_card)

    with pytest.raises(PIIDetectionError):
        api_key_pii_middleware.before_model({"messages": [api_key]}, None)


def test_business_contact_pii_is_redacted_from_model_text_output() -> None:
    message = AIMessage(content="已记录 buyer@example.com，联系电话 13800138000")

    email_result = email_pii_middleware.after_model({"messages": [message]}, None)
    phone_result = phone_number_pii_middleware.after_model({"messages": [message]}, None)

    assert "[REDACTED_EMAIL]" in str(email_result["messages"][-1].content)
    assert "[REDACTED_PHONE_NUMBER]" in str(phone_result["messages"][-1].content)
