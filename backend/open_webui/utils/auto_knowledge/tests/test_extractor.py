import pytest

from open_webui.utils.auto_knowledge.extractor import (
    CandidateExtractionError,
    parse_extraction_response,
)
from open_webui.utils.auto_knowledge.types import ChatSegment


def test_parse_extraction_response_returns_candidate_with_source_ids():
    segment = ChatSegment(
        chat_id="chat-1",
        user_id="support-user",
        user_message_id="u1",
        assistant_message_id="a1",
        user_text="客户如何申请退款？",
        assistant_text="7 天内未使用服务可以在订单详情页申请退款。",
        created_at=100,
        model_id="gpt-test",
    )
    raw = """
    {
      "question": "客户如何申请退款？",
      "answer": "7 天内未使用服务可以在订单详情页申请退款。",
      "category": "售后/退款",
      "tags": ["退款", "售后"],
      "confidence": 0.86,
      "risk_level": "low"
    }
    """

    candidate = parse_extraction_response(raw, [segment])

    assert candidate.question == "客户如何申请退款？"
    assert candidate.answer.startswith("7 天内")
    assert candidate.source_chat_ids == ["chat-1"]
    assert candidate.source_message_ids == ["u1", "a1"]
    assert candidate.confidence == 0.86


def test_parse_extraction_response_rejects_malformed_or_incomplete_output():
    segment = ChatSegment(
        chat_id="chat-1",
        user_id="support-user",
        user_message_id="u1",
        assistant_message_id="a1",
        user_text="客户如何申请退款？",
        assistant_text="7 天内未使用服务可以在订单详情页申请退款。",
        created_at=100,
        model_id="gpt-test",
    )

    with pytest.raises(CandidateExtractionError):
        parse_extraction_response('{"question": "客户如何申请退款？"}', [segment])

    with pytest.raises(CandidateExtractionError):
        parse_extraction_response("not json", [segment])
