from open_webui.utils.auto_knowledge.collector import build_segments_from_messages


def test_build_segments_from_messages_pairs_user_and_assistant_messages():
    messages = [
        {
            "id": "chat-1-u1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "user",
            "parent_id": None,
            "content": "客户如何申请退款？",
            "created_at": 100,
        },
        {
            "id": "chat-1-a1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "assistant",
            "parent_id": "chat-1-u1",
            "content": "7 天内未使用服务可以在订单详情页申请退款。",
            "created_at": 101,
            "model_id": "gpt-test",
        },
    ]

    segments = build_segments_from_messages(messages)

    assert len(segments) == 1
    assert segments[0].chat_id == "chat-1"
    assert segments[0].user_message_id == "chat-1-u1"
    assert segments[0].assistant_message_id == "chat-1-a1"
    assert segments[0].user_text == "客户如何申请退款？"
    assert segments[0].assistant_text.startswith("7 天内")


def test_build_segments_from_messages_ignores_assistant_without_user_parent():
    messages = [
        {
            "id": "chat-1-a1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "assistant",
            "parent_id": "missing-user",
            "content": "7 天内未使用服务可以在订单详情页申请退款。",
            "created_at": 101,
            "model_id": "gpt-test",
        }
    ]

    assert build_segments_from_messages(messages) == []


def test_build_segments_from_messages_pairs_database_composite_ids():
    messages = [
        {
            "id": "chat-1-u1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "user",
            "parent_id": None,
            "content": "How do I request a refund?",
            "created_at": 100,
        },
        {
            "id": "chat-1-a1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "assistant",
            "parent_id": "u1",
            "content": "Refunds are available within 7 days from order details.",
            "created_at": 101,
            "model_id": "gpt-test",
        },
    ]

    segments = build_segments_from_messages(messages)

    assert len(segments) == 1
    assert segments[0].user_message_id == "u1"
    assert segments[0].assistant_message_id == "a1"


def test_build_segments_from_messages_flattens_rich_content_blocks():
    messages = [
        {
            "id": "chat-1-u1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "user",
            "parent_id": None,
            "content": [{"type": "text", "text": "客户如何修改地址？"}],
            "created_at": 100,
        },
        {
            "id": "chat-1-a1",
            "chat_id": "chat-1",
            "user_id": "support-user",
            "role": "assistant",
            "parent_id": "chat-1-u1",
            "content": [{"type": "text", "text": "发货前可以在订单详情页修改。"}],
            "created_at": 101,
            "model_id": "gpt-test",
        },
    ]

    segments = build_segments_from_messages(messages)

    assert segments[0].user_text == "客户如何修改地址？"
    assert segments[0].assistant_text == "发货前可以在订单详情页修改。"
