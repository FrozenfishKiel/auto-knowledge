from types import SimpleNamespace

import pytest

from open_webui.models.auto_knowledge import RUN_STATUS_FAILED
from open_webui.utils.auto_knowledge import scheduler
from open_webui.utils.auto_knowledge.scheduler import OpenWebUIExtractor, ensure_model_registry
from open_webui.utils.auto_knowledge.schedules import resolve_window_ns
from open_webui.utils.auto_knowledge.types import ChatSegment


def test_resolve_window_ns_uses_job_lookback_hours():
    now_ns = 1_000_000_000_000
    job = SimpleNamespace(
        source_filter={"lookback_hours": 2},
        schedule={"rrule": "RRULE:FREQ=DAILY;INTERVAL=1"},
    )

    start_at, end_at = resolve_window_ns(job, now_ns)

    assert end_at == 1000
    assert start_at == 1000 - 2 * 60 * 60


def test_resolve_window_ns_prefers_explicit_window():
    job = SimpleNamespace(
        source_filter={"start_at": 100, "end_at": 200, "lookback_hours": 24},
        schedule={"rrule": "RRULE:FREQ=DAILY;INTERVAL=1"},
    )

    assert resolve_window_ns(job, 999_000_000_000) == (100, 200)


@pytest.mark.asyncio
async def test_ensure_model_registry_refreshes_when_model_is_missing(monkeypatch):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(MODELS={})))
    user = SimpleNamespace(id="admin-user", role="admin")
    calls = []

    async def fake_get_all_models(request_arg, user=None):
        calls.append((request_arg, user))
        request_arg.app.state.MODELS = {"openai/gpt-4o-mini": {"id": "openai/gpt-4o-mini"}}
        return list(request_arg.app.state.MODELS.values())

    monkeypatch.setattr("open_webui.utils.auto_knowledge.scheduler.get_all_models", fake_get_all_models)

    await ensure_model_registry(request, "openai/gpt-4o-mini", user)

    assert request.app.state.MODELS["openai/gpt-4o-mini"]["id"] == "openai/gpt-4o-mini"
    assert calls == [(request, user)]


@pytest.mark.asyncio
async def test_openwebui_extractor_requests_json_mode(monkeypatch):
    captured = {}

    async def fake_ensure_model_registry(request, model_id, user):
        captured["model_id"] = model_id

    async def fake_generate_chat_completion(request, form_data, user):
        captured["form_data"] = form_data
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"question":"How are refunds handled?",'
                            '"answer":"Finance Ops handles refunds within 14 days.",'
                            '"category":"support/refund",'
                            '"tags":["refund"],'
                            '"confidence":0.9,'
                            '"risk_level":"low"}'
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("open_webui.utils.auto_knowledge.scheduler.ensure_model_registry", fake_ensure_model_registry)
    monkeypatch.setattr("open_webui.utils.auto_knowledge.scheduler.generate_chat_completion", fake_generate_chat_completion)

    extractor = OpenWebUIExtractor(SimpleNamespace(state=SimpleNamespace()), "deepseek-v4-flash", SimpleNamespace())
    result = await extractor.extract(
        ChatSegment(
            chat_id="chat-1",
            user_id="user-1",
            user_message_id="u1",
            assistant_message_id="a1",
            user_text="How do refunds work?",
            assistant_text="Finance Ops handles refunds within 14 days.",
            created_at=100,
            model_id="deepseek-v4-flash",
        )
    )

    assert result.question == "How are refunds handled?"
    assert captured["model_id"] == "deepseek-v4-flash"
    assert captured["form_data"]["temperature"] == 0
    assert captured["form_data"]["response_format"] == {"type": "json_object"}


def _job(extractor=None):
    return SimpleNamespace(
        id="job-1",
        user_id="admin-user",
        target_knowledge_id="kb-1",
        source_filter={"start_at": 100, "end_at": 200, "limit": 10},
        schedule={},
        extractor=extractor or {"model_id": "deepseek-v4-flash"},
    )


def _segment():
    return ChatSegment(
        chat_id="chat-1",
        user_id="user-1",
        user_message_id="u1",
        assistant_message_id="a1",
        user_text="How do refunds work?",
        assistant_text="Finance Ops handles refunds within 14 days.",
        created_at=100,
        model_id="deepseek-v4-flash",
    )


def _patch_execute_job_dependencies(monkeypatch, pipeline_result, inserted=None):
    updates = []
    captured = {}

    class FakeRuns:
        async def insert(self, job_id):
            return SimpleNamespace(id="run-1", job_id=job_id)

        async def update_by_id(self, run_id, data):
            updates.append((run_id, data))
            return SimpleNamespace(id=run_id, **data)

    class FakeCandidates:
        async def get_existing_for_target(self, target_knowledge_id):
            return []

        async def insert_many(self, job_id, run_id, target_knowledge_id, candidates):
            return inserted if inserted is not None else list(candidates)

    class FakeJobs:
        async def mark_finished(self, job_id, next_run_at):
            captured["marked_finished"] = (job_id, next_run_at)

    async def fake_get_user_by_id(user_id):
        return SimpleNamespace(id=user_id, role="admin")

    async def fake_collect_segments_from_chat_messages(**kwargs):
        captured["collect_kwargs"] = kwargs
        return [_segment()]

    async def fake_run_extraction_pipeline(segments, extractor, existing_candidates=None, extraction_concurrency=0):
        captured["pipeline_kwargs"] = {
            "segments": segments,
            "extractor": extractor,
            "existing_candidates": existing_candidates,
            "extraction_concurrency": extraction_concurrency,
        }
        return pipeline_result

    async def fake_publish_event(*args, **kwargs):
        captured.setdefault("events", []).append((args, kwargs))

    monkeypatch.setattr(scheduler, "AutoKnowledgeRuns", FakeRuns())
    monkeypatch.setattr(scheduler, "AutoKnowledgeCandidates", FakeCandidates())
    monkeypatch.setattr(scheduler, "AutoKnowledgeJobs", FakeJobs())
    monkeypatch.setattr(scheduler.Users, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(scheduler, "collect_segments_from_chat_messages", fake_collect_segments_from_chat_messages)
    monkeypatch.setattr(scheduler, "run_extraction_pipeline", fake_run_extraction_pipeline)
    monkeypatch.setattr(scheduler, "publish_event", fake_publish_event)
    return captured, updates


@pytest.mark.asyncio
async def test_execute_auto_knowledge_job_passes_extractor_concurrency_to_pipeline(monkeypatch):
    result = SimpleNamespace(
        input_count=1,
        cleaned_count=1,
        candidates=[],
        duplicate_count=0,
        failed_count=0,
        errors=[],
    )
    captured, updates = _patch_execute_job_dependencies(monkeypatch, result)

    await scheduler.execute_auto_knowledge_job(SimpleNamespace(), _job({"model_id": "deepseek-v4-flash", "concurrency": 12}))

    assert captured["pipeline_kwargs"]["extraction_concurrency"] == 12
    assert updates[0][1]["status"] == "success"


@pytest.mark.asyncio
async def test_execute_auto_knowledge_job_marks_all_extraction_failures_as_failed(monkeypatch):
    result = SimpleNamespace(
        input_count=2,
        cleaned_count=2,
        candidates=[],
        duplicate_count=0,
        failed_count=2,
        errors=["bad output", "timeout"],
    )
    _, updates = _patch_execute_job_dependencies(monkeypatch, result, inserted=[])

    await scheduler.execute_auto_knowledge_job(SimpleNamespace(), _job())

    assert updates[0][1]["status"] == RUN_STATUS_FAILED
    assert updates[0][1]["generated_count"] == 0
