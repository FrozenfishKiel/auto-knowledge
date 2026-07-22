from types import SimpleNamespace

import pytest

from open_webui.models.auto_knowledge import (
    sanitize_source_preview_content,
)
from open_webui.utils.auto_knowledge.runner import run_extraction_pipeline
from open_webui.utils.auto_knowledge.types import ChatSegment, ExtractedKnowledge


class FakeExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        return ExtractedKnowledge(
            question="How do enterprise refunds work?",
            answer="Enterprise annual plans can request a prorated refund within 14 days through Finance Ops.",
            category="Finance/Refunds",
            tags=["refund", "enterprise"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.92,
            risk_level="low",
            metadata={
                "user_id": segment.user_id,
                "source_roles": ["user", "assistant"],
                "model_id": segment.model_id,
            },
        )


@pytest.mark.asyncio
async def test_business_flow_masks_pii_before_candidate_generation():
    segment = ChatSegment(
        chat_id="chat-support-1",
        user_id="support-user-1",
        user_message_id="u1",
        assistant_message_id="a1",
        user_text="Customer 13812345678 asked where to request an enterprise refund.",
        assistant_text="Finance Ops handles enterprise annual-plan refunds within 14 days. Email finance@example.com for escalation.",
        created_at=100,
        model_id="gpt-test",
    )

    result = await run_extraction_pipeline([segment], FakeExtractor())

    assert result.generated_count == 1
    assert result.cleaned_count == 1
    assert result.failed_count == 0
    assert result.candidates[0].answer == (
        "Enterprise annual plans can request a prorated refund within 14 days through Finance Ops."
    )


def test_candidate_source_preview_should_hide_sensitive_content():
    content = sanitize_source_preview_content(
        "Call me at 13812345678 or email finance@example.com with sk-testsecretsecretsecret."
    )
    assert "[PHONE]" in content
    assert "[EMAIL]" in content
    assert "[API_KEY]" in content
