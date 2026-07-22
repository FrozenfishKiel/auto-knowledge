from open_webui.utils.auto_knowledge.deduplicator import find_duplicate
from open_webui.utils.auto_knowledge.types import ExtractedKnowledge


def test_find_duplicate_matches_normalized_question_text():
    candidate = ExtractedKnowledge(
        question="客户如何申请退款？",
        answer="7 天内未使用服务可以申请退款。",
        category="售后/退款",
        tags=["退款"],
        source_chat_ids=["chat-1"],
        source_message_ids=["u1", "a1"],
        confidence=0.9,
        risk_level="low",
    )
    existing = [
        ExtractedKnowledge(
            question="客户如何申请退款",
            answer="订单 7 天内可申请退款。",
            category="售后/退款",
            tags=["退款"],
            source_chat_ids=["chat-0"],
            source_message_ids=["u0", "a0"],
            confidence=0.8,
            risk_level="low",
        )
    ]

    duplicate = find_duplicate(candidate, existing)

    assert duplicate is existing[0]


def test_find_duplicate_ignores_unrelated_questions():
    candidate = ExtractedKnowledge(
        question="客户如何申请退款？",
        answer="7 天内未使用服务可以申请退款。",
        category="售后/退款",
        tags=["退款"],
        source_chat_ids=["chat-1"],
        source_message_ids=["u1", "a1"],
        confidence=0.9,
        risk_level="low",
    )
    existing = [
        ExtractedKnowledge(
            question="客户如何修改收货地址？",
            answer="发货前可以在订单详情页修改地址。",
            category="订单/地址",
            tags=["地址"],
            source_chat_ids=["chat-0"],
            source_message_ids=["u0", "a0"],
            confidence=0.8,
            risk_level="low",
        )
    ]

    assert find_duplicate(candidate, existing) is None
