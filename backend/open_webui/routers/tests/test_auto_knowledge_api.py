from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from open_webui.internal.db import get_async_session
from open_webui.models.auto_knowledge import (
    AutoKnowledgeCandidateDetailResponse,
    AutoKnowledgeCandidateModel,
    AutoKnowledgeJobModel,
    AutoKnowledgeSourcePreviewModel,
    CANDIDATE_STATUS_PENDING,
    CANDIDATE_STATUS_PUBLISHED,
)
from open_webui.routers import auto_knowledge
from open_webui.utils.auth import get_admin_user


def _job(**overrides):
    data = {
        "id": "job-1",
        "user_id": "admin-1",
        "name": "Weekly Support Knowledge",
        "description": None,
        "target_knowledge_id": "kb-1",
        "source_filter": {"group_ids": ["support"]},
        "schedule": {},
        "extractor": {"model_id": "gpt-test"},
        "review_policy": {"mode": "manual"},
        "is_active": True,
        "is_running": False,
        "last_run_at": None,
        "next_run_at": None,
        "created_at": 1,
        "updated_at": 1,
    }
    return AutoKnowledgeJobModel(**{**data, **overrides})


def _candidate(**overrides):
    data = {
        "id": "cand-1",
        "job_id": "job-1",
        "run_id": "run-1",
        "target_knowledge_id": "kb-1",
        "question": "How do refunds work?",
        "answer": "Refunds are available within 7 days.",
        "category": "Support",
        "tags": ["refund"],
        "confidence": 91,
        "risk_level": "low",
        "status": CANDIDATE_STATUS_PENDING,
        "created_at": 1,
        "updated_at": 1,
    }
    return AutoKnowledgeCandidateModel(**{**data, **overrides})


class FakeKnowledgeTable:
    async def get_knowledge_by_id(self, id, db=None):
        return SimpleNamespace(id=id, meta={})


class FakeJobTable:
    async def insert(self, user_id, form, next_run_at, db=None):
        return _job(user_id=user_id, source_filter=form.source_filter)

    async def get_by_id(self, id, db=None):
        return _job(id=id)

    async def mark_running(self, id, db=None):
        return None


class FakeCandidateTable:
    def __init__(self, status=CANDIDATE_STATUS_PENDING):
        self.status = status

    async def get_by_id(self, id, db=None):
        return _candidate(id=id, status=self.status)

    async def get_detail_by_id(self, id, db=None):
        return AutoKnowledgeCandidateDetailResponse(
            **_candidate(id=id).model_dump(),
            sources=[
                AutoKnowledgeSourcePreviewModel(
                    id="src-1",
                    candidate_id=id,
                    chat_id="chat-1",
                    message_id="msg-1",
                    user_id="support-user",
                    role="user",
                    content="How do refunds work?",
                    created_at=1,
                )
            ],
        )


def _build_client(monkeypatch, *, admin=True, candidate_status=CANDIDATE_STATUS_PENDING):
    app = FastAPI()
    app.include_router(auto_knowledge.router, prefix="/api/v1/auto-knowledge")

    async def fake_db():
        return None

    def fake_admin_user():
        if not admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access prohibited")
        return SimpleNamespace(id="admin-1", role="admin")

    async def noop_publish_event(*args, **kwargs):
        return None

    monkeypatch.setattr(auto_knowledge, "Knowledges", FakeKnowledgeTable())
    monkeypatch.setattr(auto_knowledge, "AutoKnowledgeJobs", FakeJobTable())
    monkeypatch.setattr(auto_knowledge, "AutoKnowledgeCandidates", FakeCandidateTable(candidate_status))
    monkeypatch.setattr(auto_knowledge, "publish_event", noop_publish_event)
    app.dependency_overrides[get_async_session] = fake_db
    app.dependency_overrides[get_admin_user] = fake_admin_user
    return TestClient(app)


def test_non_admin_users_are_denied_auto_knowledge_api(monkeypatch):
    client = _build_client(monkeypatch, admin=False)

    response = client.get("/api/v1/auto-knowledge/")

    assert response.status_code == 401


def test_admin_can_create_job_with_group_source_filter(monkeypatch):
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/auto-knowledge/create",
        json={
            "name": "Weekly Support Knowledge",
            "target_knowledge_id": "kb-1",
            "source_filter": {"group_ids": ["support"]},
            "schedule": {},
            "extractor": {"model_id": "gpt-test"},
        },
    )

    assert response.status_code == 200
    assert response.json()["source_filter"]["group_ids"] == ["support"]


def test_manual_run_rejects_concurrent_job_claim(monkeypatch):
    client = _build_client(monkeypatch)

    response = client.post("/api/v1/auto-knowledge/job-1/run")

    assert response.status_code == 409


def test_candidate_detail_returns_source_preview_rows(monkeypatch):
    client = _build_client(monkeypatch)

    response = client.get("/api/v1/auto-knowledge/candidates/cand-1")

    assert response.status_code == 200
    assert response.json()["sources"][0]["chat_id"] == "chat-1"
    assert response.json()["sources"][0]["content"] == "How do refunds work?"


@pytest.mark.parametrize("candidate_status", [CANDIDATE_STATUS_PENDING, CANDIDATE_STATUS_PUBLISHED])
def test_publish_endpoint_is_status_gated_and_idempotent(monkeypatch, candidate_status):
    client = _build_client(monkeypatch, candidate_status=candidate_status)

    response = client.post("/api/v1/auto-knowledge/candidates/cand-1/publish")

    if candidate_status == CANDIDATE_STATUS_PENDING:
        assert response.status_code == 400
    else:
        assert response.status_code == 200
        assert response.json()["status"] == CANDIDATE_STATUS_PUBLISHED
