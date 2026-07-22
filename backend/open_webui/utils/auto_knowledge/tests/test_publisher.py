import sys
from types import SimpleNamespace

import pytest

from open_webui.utils.auto_knowledge.publisher import publish_candidate_to_knowledge, render_candidate_markdown


def test_render_candidate_markdown_includes_reviewable_metadata():
    candidate = SimpleNamespace(
        id="cand-1",
        job_id="job-1",
        run_id="run-1",
        target_knowledge_id="kb-1",
        question="How do customers request refunds?",
        answer="Customers can request refunds from order details within 7 days.",
        category="Support/Refunds",
        tags=["refund", "support"],
        confidence=86,
        risk_level="low",
        status="pending_review",
        created_at=1,
        updated_at=1,
    )

    content = render_candidate_markdown(candidate)

    assert content.startswith("# How do customers request refunds?")
    assert "Customers can request refunds" in content
    assert "- Category: Support/Refunds" in content
    assert "- Tags: refund, support" in content
    assert "- Auto Knowledge candidate: cand-1" in content


@pytest.mark.asyncio
async def test_publish_candidate_processes_file_into_target_knowledge(monkeypatch):
    import open_webui.models.auto_knowledge as auto_knowledge_models

    calls = {
        "processed_collection": None,
        "process_db": None,
        "attached": None,
        "attach_db": None,
        "published_count_run": None,
    }

    class FakeFileForm:
        def __init__(self, **data):
            self.__dict__.update(data)

    class FakeProcessFileForm:
        def __init__(self, **data):
            self.__dict__.update(data)

    class FakeFiles:
        async def insert_new_file(self, user_id, form):
            return SimpleNamespace(id=form.id)

    class FakeKnowledge:
        async def add_file_to_knowledge_by_id(self, knowledge_id, file_id, user_id, db=None):
            calls["attached"] = (knowledge_id, file_id, user_id)
            calls["attach_db"] = db
            return SimpleNamespace(id=file_id)

    class FakeCandidates:
        async def update_by_id(self, id, data, db=None):
            values = {**candidate.__dict__, **data}
            return SimpleNamespace(
                **values,
            )

    class FakeRuns:
        async def increment_published_count(self, id, db=None):
            calls["published_count_run"] = id
            return None

    async def fake_process_file(request, form, user, db=None):
        calls["processed_collection"] = form.collection_name
        calls["process_db"] = db
        return SimpleNamespace(status=True)

    class FakeDbContext:
        async def __aenter__(self):
            return "db-session"

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "open_webui.models.files",
        SimpleNamespace(FileForm=FakeFileForm, Files=FakeFiles()),
    )
    monkeypatch.setitem(
        sys.modules,
        "open_webui.models.knowledge",
        SimpleNamespace(Knowledges=FakeKnowledge()),
    )
    monkeypatch.setitem(
        sys.modules,
        "open_webui.routers.retrieval",
        SimpleNamespace(ProcessFileForm=FakeProcessFileForm, process_file=fake_process_file),
    )
    monkeypatch.setitem(
        sys.modules,
        "open_webui.internal.db",
        SimpleNamespace(get_async_db=lambda: FakeDbContext()),
    )
    monkeypatch.setattr(auto_knowledge_models, "AutoKnowledgeCandidates", FakeCandidates())
    monkeypatch.setattr(auto_knowledge_models, "AutoKnowledgeRuns", FakeRuns())

    candidate = SimpleNamespace(
        id="cand-1",
        job_id="job-1",
        run_id="run-1",
        target_knowledge_id="kb-1",
        question="How do customers request refunds?",
        answer="Customers can request refunds from order details within 7 days.",
        category="Support/Refunds",
        tags=["refund", "support"],
        confidence=86,
        risk_level="low",
        status="approved",
        meta={},
    )
    user = SimpleNamespace(id="admin-1")
    request = SimpleNamespace()

    published = await publish_candidate_to_knowledge(candidate, user, request=request)

    assert published.status == "published"
    assert calls["processed_collection"] == "kb-1"
    assert calls["process_db"] == "db-session"
    assert calls["attached"][0] == "kb-1"
    assert calls["attach_db"] == "db-session"
    assert calls["published_count_run"] == "run-1"
