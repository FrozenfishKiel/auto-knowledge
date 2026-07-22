from open_webui.utils.auto_knowledge.cleaner import clean_segments, mask_sensitive_text
from open_webui.utils.auto_knowledge.types import ChatSegment


def test_mask_sensitive_text_replaces_common_private_values():
    text = (
        "客户手机号 13812345678，邮箱 buyer@example.com，"
        "订单号 ORD-20260722-8899，密钥 sk-1234567890abcdef1234567890abcdef。"
    )

    masked = mask_sensitive_text(text)

    assert "13812345678" not in masked
    assert "buyer@example.com" not in masked
    assert "ORD-20260722-8899" not in masked
    assert "sk-1234567890abcdef1234567890abcdef" not in masked
    assert "[PHONE]" in masked
    assert "[EMAIL]" in masked
    assert "[ORDER_ID]" in masked
    assert "[API_KEY]" in masked


def test_mask_sensitive_text_replaces_tokens_and_social_ids():
    text = (
        "Bearer abcdefghijklmnopqrstuvwxyz1234567890 "
        "eyJabcdefghijklmnop.eyJqrstuvwxyz12345.signature67890 "
        "QQ:12345678 wechat:openwebui_2026"
    )

    masked = mask_sensitive_text(text)

    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in masked
    assert "eyJabcdefghijklmnop" not in masked
    assert "12345678" not in masked
    assert "openwebui_2026" not in masked
    assert "[BEARER_TOKEN]" in masked
    assert "[JWT]" in masked
    assert "[QQ]" in masked
    assert "[WECHAT]" in masked


def test_clean_segments_keeps_business_qa_and_drops_low_value_segments():
    segments = [
        ChatSegment(
            chat_id="chat-1",
            user_id="support-user",
            user_message_id="u1",
            assistant_message_id="a1",
            user_text="客户说手机号 13812345678 的订单如何退款？",
            assistant_text="7 天内未使用服务可以在订单详情页申请退款。",
            created_at=100,
            model_id="gpt-test",
        ),
        ChatSegment(
            chat_id="chat-2",
            user_id="support-user",
            user_message_id="u2",
            assistant_message_id="a2",
            user_text="你好",
            assistant_text="你好呀",
            created_at=110,
            model_id="gpt-test",
        ),
        ChatSegment(
            chat_id="chat-3",
            user_id="support-user",
            user_message_id="u3",
            assistant_message_id="a3",
            user_text="这个报错是什么意思？",
            assistant_text="",
            created_at=120,
            model_id="gpt-test",
            error={"message": "provider failed"},
        ),
    ]

    cleaned = clean_segments(segments)

    assert len(cleaned) == 1
    assert cleaned[0].chat_id == "chat-1"
    assert "13812345678" not in cleaned[0].user_text
    assert "[PHONE]" in cleaned[0].user_text
