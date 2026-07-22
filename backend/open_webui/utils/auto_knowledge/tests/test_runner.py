import asyncio
import time

import pytest

from open_webui.utils.auto_knowledge.extractor import CandidateExtractionError
from open_webui.utils.auto_knowledge.runner import ExtractionPipelineResult, run_extraction_pipeline
from open_webui.utils.auto_knowledge.types import ChatSegment, ExtractedKnowledge


class FakeExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        return ExtractedKnowledge(
            question="客户如何申请退款？",
            answer="7 天内未使用服务可以在订单详情页申请退款。",
            category="售后/退款",
            tags=["退款", "售后"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


class MalformedExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        raise CandidateExtractionError("bad output")


class SlowTrackingExtractor:
    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.05)
        self.active -= 1
        return ExtractedKnowledge(
            question=f"Question {segment.chat_id}",
            answer=f"Answer {segment.chat_id}",
            category="benchmark",
            tags=["benchmark"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


class MixedFailureExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        await asyncio.sleep(0.01)
        if segment.chat_id == "chat-fail":
            raise CandidateExtractionError("single extraction failed")
        return ExtractedKnowledge(
            question=f"Question {segment.chat_id}",
            answer=f"Answer {segment.chat_id}",
            category="benchmark",
            tags=["benchmark"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


class DuplicateQuestionExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        if segment.chat_id == "chat-1":
            await asyncio.sleep(0.03)
        return ExtractedKnowledge(
            question="Same reusable policy?",
            answer=f"Answer from {segment.chat_id}",
            category="benchmark",
            tags=["benchmark"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


class OutOfOrderExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        delay = {"chat-1": 0.03, "chat-2": 0.01, "chat-3": 0.02}.get(segment.chat_id, 0)
        await asyncio.sleep(delay)
        return ExtractedKnowledge(
            question=f"Question {segment.chat_id}",
            answer=f"Answer {segment.chat_id}",
            category="benchmark",
            tags=["benchmark"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


class MixedFailureAndDuplicateExtractor:
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        if segment.chat_id == "chat-fail":
            raise CandidateExtractionError("single extraction failed")
        question = "Duplicate policy?" if segment.chat_id in {"chat-dup-1", "chat-dup-2"} else f"Question {segment.chat_id}"
        return ExtractedKnowledge(
            question=question,
            answer=f"Answer from {segment.chat_id}",
            category="benchmark",
            tags=["benchmark"],
            source_chat_ids=[segment.chat_id],
            source_message_ids=[segment.user_message_id, segment.assistant_message_id],
            confidence=0.86,
            risk_level="low",
        )


def make_segment(idx: int | str) -> ChatSegment:
    return ChatSegment(
        chat_id=f"chat-{idx}",
        user_id="support-user",
        user_message_id=f"u{idx}",
        assistant_message_id=f"a{idx}",
        user_text=f"How should business case {idx} be handled?",
        assistant_text=f"Business case {idx} should be handled by the operations team within 2 days.",
        created_at=100,
        model_id="gpt-test",
    )


@pytest.mark.asyncio
async def test_run_extraction_pipeline_returns_candidates_and_counts_filtered_segments():
    segments = [
        ChatSegment(
            chat_id="chat-1",
            user_id="support-user",
            user_message_id="u1",
            assistant_message_id="a1",
            user_text="客户手机号 13812345678 的订单如何申请退款？",
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
            created_at=101,
            model_id="gpt-test",
        ),
    ]

    result = await run_extraction_pipeline(segments, FakeExtractor())

    assert isinstance(result, ExtractionPipelineResult)
    assert result.input_count == 2
    assert result.cleaned_count == 1
    assert result.generated_count == 1
    assert result.failed_count == 0
    assert result.duplicate_count == 0
    assert result.candidates[0].question == "客户如何申请退款？"


@pytest.mark.asyncio
async def test_run_extraction_pipeline_tracks_extractor_failures():
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

    result = await run_extraction_pipeline([segment], MalformedExtractor())

    assert result.generated_count == 0
    assert result.failed_count == 1
    assert "bad output" in result.errors[0]


@pytest.mark.asyncio
async def test_run_extraction_pipeline_skips_existing_duplicates():
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
    existing = [
        ExtractedKnowledge(
            question="客户如何申请退款",
            answer="已有退款答案。",
            category="售后/退款",
            tags=["退款"],
            source_chat_ids=["old-chat"],
            source_message_ids=["old-u", "old-a"],
            confidence=0.9,
            risk_level="low",
        )
    ]

    result = await run_extraction_pipeline([segment], FakeExtractor(), existing_candidates=existing)

    assert result.generated_count == 0
    assert result.duplicate_count == 1
    assert result.candidates == []


@pytest.mark.asyncio
async def test_run_extraction_pipeline_extracts_with_bounded_concurrency():
    segments = [make_segment(idx) for idx in range(6)]
    extractor = SlowTrackingExtractor()

    started_at = time.perf_counter()
    result = await run_extraction_pipeline(segments, extractor, extraction_concurrency=3)
    duration = time.perf_counter() - started_at

    assert result.generated_count == 6
    assert result.failed_count == 0
    assert extractor.max_active == 3
    assert duration < 0.25


@pytest.mark.asyncio
async def test_run_extraction_pipeline_isolates_single_concurrent_extraction_failure():
    segments = [make_segment(1), make_segment("fail"), make_segment(2)]

    result = await run_extraction_pipeline(segments, MixedFailureExtractor(), extraction_concurrency=3)

    assert result.generated_count == 2
    assert result.failed_count == 1
    assert "single extraction failed" in result.errors[0]
    assert [candidate.question for candidate in result.candidates] == ["Question chat-1", "Question chat-2"]


@pytest.mark.asyncio
async def test_run_extraction_pipeline_deduplicates_in_input_order_after_concurrent_extraction():
    segments = [make_segment(1), make_segment(2)]

    result = await run_extraction_pipeline(segments, DuplicateQuestionExtractor(), extraction_concurrency=2)

    assert result.generated_count == 1
    assert result.duplicate_count == 1
    assert result.candidates[0].answer == "Answer from chat-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured_concurrency", "expected_max_active"),
    [(0, 1), (-5, 1), (None, 1), (99, 32)],
)
async def test_run_extraction_pipeline_clamps_concurrency_bounds(configured_concurrency, expected_max_active):
    segments = [make_segment(idx) for idx in range(40)]
    extractor = SlowTrackingExtractor()

    result = await run_extraction_pipeline(
        segments,
        extractor,
        extraction_concurrency=configured_concurrency,
    )

    assert result.generated_count == 40
    assert extractor.max_active == expected_max_active


@pytest.mark.asyncio
async def test_run_extraction_pipeline_preserves_candidate_order_when_concurrent_tasks_finish_out_of_order():
    segments = [make_segment(1), make_segment(2), make_segment(3)]

    result = await run_extraction_pipeline(segments, OutOfOrderExtractor(), extraction_concurrency=3)

    assert [candidate.answer for candidate in result.candidates] == [
        "Answer chat-1",
        "Answer chat-2",
        "Answer chat-3",
    ]


@pytest.mark.asyncio
async def test_run_extraction_pipeline_keeps_dedup_stable_with_mixed_failures_and_duplicates():
    segments = [make_segment("dup-1"), make_segment("fail"), make_segment("unique"), make_segment("dup-2")]

    result = await run_extraction_pipeline(
        segments,
        MixedFailureAndDuplicateExtractor(),
        extraction_concurrency=4,
    )

    assert result.generated_count == 2
    assert result.failed_count == 1
    assert result.duplicate_count == 1
    assert [candidate.answer for candidate in result.candidates] == [
        "Answer from chat-dup-1",
        "Answer from chat-unique",
    ]


@pytest.mark.asyncio
async def test_run_extraction_pipeline_pressure_limits_active_extractors():
    segments = [make_segment(idx) for idx in range(100)]
    extractor = SlowTrackingExtractor()

    result = await run_extraction_pipeline(segments, extractor, extraction_concurrency=12)

    assert result.generated_count == 100
    assert result.failed_count == 0
    assert extractor.max_active == 12
