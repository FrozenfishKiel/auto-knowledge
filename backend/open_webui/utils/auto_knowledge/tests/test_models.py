from open_webui.models.auto_knowledge import (
    AutoKnowledgeCandidateDetailResponse,
    AutoKnowledgeRunModel,
    AutoKnowledgeSourcePreviewModel,
)


def test_run_model_exposes_duration_fields_when_finished():
    run = AutoKnowledgeRunModel(
        id="run-1",
        job_id="job-1",
        status="success",
        started_at=1_000,
        finished_at=1_750,
        created_at=1_000,
        updated_at=1_750,
    )

    assert run.duration_ns == 750
    assert run.duration_ms == 0


def test_candidate_detail_response_includes_source_rows():
    detail = AutoKnowledgeCandidateDetailResponse(
        id="cand-1",
        job_id="job-1",
        run_id="run-1",
        target_knowledge_id="kb-1",
        question="How do refunds work?",
        answer="Refunds are available within 7 days.",
        confidence=91,
        risk_level="low",
        status="pending_review",
        created_at=1,
        updated_at=1,
        sources=[
            AutoKnowledgeSourcePreviewModel(
                id="src-1",
                candidate_id="cand-1",
                chat_id="chat-1",
                message_id="msg-1",
                user_id="support-user",
                role="user",
                content="How do refunds work?",
                created_at=1,
            )
        ],
    )

    assert detail.sources[0].chat_id == "chat-1"
    assert detail.sources[0].content == "How do refunds work?"
