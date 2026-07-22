from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


BASE_URL = os.environ.get("OPEN_WEBUI_BASE_URL", "http://127.0.0.1:8081")
ADMIN_EMAIL = os.environ.get("AUTO_KNOWLEDGE_ADMIN_EMAIL", "ak-admin@example.com")
ADMIN_PASSWORD = os.environ.get("AUTO_KNOWLEDGE_ADMIN_PASSWORD", "AutoKnowledge123!")
MODEL_ID = os.environ.get("AUTO_KNOWLEDGE_MODEL_ID", "gpt-4o-mini")


def load_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = Path(".env.local")
    if not env_path.exists():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def summarize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if "key" in k.lower() or "token" in k.lower() else summarize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [summarize(v) for v in value[:8]]
    return value


class Harness:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.client = httpx.Client(base_url=BASE_URL, timeout=90.0, follow_redirects=True)
        self.token: str | None = None

    def record(self, step: str, status: str, detail: Any = None) -> None:
        event = {"step": step, "status": status, "detail": summarize(detail)}
        self.events.append(event)
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers = {**headers, "Authorization": f"Bearer {self.token}"}
        response = self.client.request(method, path, headers=headers, **kwargs)
        if response.status_code >= 400:
            try:
                body: Any = response.json()
            except Exception:
                body = response.text[:1000]
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {body}")
        return response

    def auth(self) -> dict[str, Any]:
        payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        try:
            data = self.client.post("/api/v1/auths/signin", json=payload).json()
            if "token" not in data:
                raise RuntimeError(data)
            self.record("auth.signin", "ok", {"email": ADMIN_EMAIL, "role": data.get("role")})
        except Exception as signin_error:
            signup = {"name": "Auto Knowledge Admin", **payload}
            response = self.client.post("/api/v1/auths/signup", json=signup)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"signin failed ({signin_error}); signup failed {response.status_code}: {response.text[:1000]}"
                )
            data = response.json()
            self.record("auth.signup", "ok", {"email": ADMIN_EMAIL, "role": data.get("role")})
        self.token = data["token"]
        return data

    def run(self) -> int:
        env = load_local_env()
        api_key = env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing from .env.local or environment")

        health = self.client.get("/health").json()
        self.record("backend.health", "ok", health)

        user = self.auth()
        if user.get("role") != "admin":
            raise RuntimeError(f"harness user must be admin, got {user.get('role')}")

        config_payload = {
            "ENABLE_OPENAI_API": True,
            "OPENAI_API_BASE_URLS": [env.get("OPENAI_API_BASE_URL", "https://api.openai.com/v1")],
            "OPENAI_API_KEYS": [api_key],
            "OPENAI_API_CONFIGS": {},
        }
        self.request("POST", "/openai/config/update", json=config_payload)
        self.record("openai.config", "ok", {"base_urls": config_payload["OPENAI_API_BASE_URLS"]})

        models = self.request("GET", "/openai/models").json().get("data", [])
        model_ids = [item.get("id") for item in models if isinstance(item, dict)]
        chosen_model = MODEL_ID if MODEL_ID in model_ids else (model_ids[0] if model_ids else MODEL_ID)
        self.record("openai.models", "ok", {"count": len(model_ids), "chosen_model": chosen_model})

        marker = f"AK-HARNESS-{uuid4().hex[:8]}"
        knowledge = self.request(
            "POST",
            "/api/v1/knowledge/create",
            json={
                "name": f"Company Support KB {marker}",
                "description": "Auto Knowledge harness target knowledge base",
                "access_grants": [],
            },
        ).json()
        kb_id = knowledge["id"]
        self.record("knowledge.create", "ok", {"id": kb_id, "name": knowledge.get("name")})

        # Keep both sides of the seeded exchange safely inside the collector's
        # default lookback window. The job resolves end_at at run-request time,
        # so future-dated assistant messages will be invisible to the run.
        now = int(time.time()) - 60
        user_msg_id = f"user-{marker}"
        assistant_msg_id = f"assistant-{marker}"
        business_answer = (
            f"{marker}：企业年度套餐退款由 Finance Ops 处理，按未使用月份比例退款，"
            "标准 SLA 为 14 个自然日；超过 5 万元或客户威胁法务时升级到 finance-ops-escalation。"
        )
        chat = self.request(
            "POST",
            "/api/v1/chats/new",
            json={
                "chat": {
                    "title": f"Enterprise refund ops {marker}",
                    "models": [chosen_model],
                    "history": {
                        "currentId": assistant_msg_id,
                        "messages": {
                            user_msg_id: {
                                "id": user_msg_id,
                                "role": "user",
                                "content": (
                                    "客户问企业年度套餐退款规则。内部手机号 13800138000，"
                                    "不要把这类敏感信息写进知识库。"
                                ),
                                "timestamp": now,
                                "childrenIds": [assistant_msg_id],
                            },
                            assistant_msg_id: {
                                "id": assistant_msg_id,
                                "parentId": user_msg_id,
                                "role": "assistant",
                                "model": chosen_model,
                                "content": business_answer,
                                "timestamp": now + 1,
                                "childrenIds": [],
                            },
                        },
                    },
                }
            },
        ).json()
        self.record("chat.seed", "ok", {"chat_id": chat["id"], "marker": marker})

        job = self.request(
            "POST",
            "/api/v1/auto-knowledge/create",
            json={
                "name": f"Weekly Support Knowledge {marker}",
                "description": "Harness job: harvest support chat into knowledge base",
                "target_knowledge_id": kb_id,
                "source_filter": {
                    "lookback_hours": 168,
                    "limit": 100,
                    "model_ids": [chosen_model],
                    "user_ids": [user["id"]],
                },
                "schedule": {},
                "extractor": {"model_id": chosen_model},
                "review_policy": {"mode": "manual"},
                "is_active": True,
            },
        ).json()
        job_id = job["id"]
        self.record("auto_knowledge.job.create", "ok", {"job_id": job_id})

        self.request("POST", f"/api/v1/auto-knowledge/{job_id}/run")
        self.record("auto_knowledge.job.run", "requested", {"job_id": job_id})

        final_run = None
        for _ in range(45):
            runs = self.request("GET", f"/api/v1/auto-knowledge/{job_id}/runs").json()
            if runs:
                final_run = runs[0]
                if final_run.get("finished_at") or final_run.get("status") in {"success", "partial_success", "failed"}:
                    break
            time.sleep(2)
        self.record("auto_knowledge.run.poll", "ok", final_run)
        if not final_run or final_run.get("status") not in {"success", "partial_success"}:
            raise RuntimeError(f"auto knowledge run failed or timed out: {final_run}")

        candidate_list = self.request(
            "GET",
            f"/api/v1/auto-knowledge/candidates/list?job_id={job_id}",
        ).json()
        candidates = candidate_list.get("items", [])
        self.record("auto_knowledge.candidates.list", "ok", {"total": candidate_list.get("total")})
        if not candidates:
            raise RuntimeError("run succeeded but produced no candidates")

        candidate_id = candidates[0]["id"]
        detail = self.request("GET", f"/api/v1/auto-knowledge/candidates/{candidate_id}").json()
        source_preview = "\n".join((source.get("content") or "") for source in detail.get("sources", []))
        self.record(
            "auto_knowledge.candidate.detail",
            "ok",
            {
                "candidate_id": candidate_id,
                "question": detail.get("question"),
                "sensitive_masked": "13800138000" not in source_preview,
            },
        )
        if "13800138000" in source_preview:
            raise RuntimeError("source preview leaked sensitive phone number")

        published = self.request(
            "POST",
            f"/api/v1/auto-knowledge/candidates/{candidate_id}/approve?publish=true",
            json={
                "question": f"{marker} 企业年度套餐退款怎么处理？",
                "answer": business_answer,
                "category": "support/refund",
                "tags": ["enterprise", "refund", "finance-ops", marker],
            },
        ).json()
        self.record(
            "auto_knowledge.candidate.publish",
            "ok" if published.get("status") == "published" else "failed",
            {"status": published.get("status"), "file_id": published.get("published_file_id"), "meta": published.get("meta")},
        )
        if published.get("status") != "published":
            raise RuntimeError(f"candidate was not published: {published}")

        files = self.request("GET", f"/api/v1/knowledge/{kb_id}/files?include_content=true&limit=5").json()
        self.record("knowledge.files", "ok", {"total": files.get("total"), "items": files.get("items")})

        retrieval = self.request(
            "POST",
            "/api/v1/retrieval/query/collection",
            json={"collection_names": [kb_id], "query": "企业年度套餐退款 SLA Finance Ops", "k": 3, "hybrid": False},
        ).json()
        retrieval_text = json.dumps(retrieval, ensure_ascii=False)
        self.record(
            "retrieval.query",
            "ok",
            {"mentions_marker": marker in retrieval_text, "mentions_finance_ops": "Finance Ops" in retrieval_text},
        )
        if marker not in retrieval_text:
            raise RuntimeError("retrieval query did not return the newly published knowledge marker")

        baseline = self.request(
            "POST",
            "/openai/chat/completions",
            json={
                "model": chosen_model,
                "messages": [{"role": "user", "content": "企业年度套餐退款应该找谁处理？只回答你知道的事实。"}],
                "temperature": 0,
                "max_tokens": 200,
            },
        ).json()
        self.record("llm.baseline", "ok", {"content": baseline.get("choices", [{}])[0].get("message", {}).get("content", "")[:500]})

        grounded = self.request(
            "POST",
            "/openai/chat/completions",
            json={
                "model": chosen_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Use this company knowledge when answering:\n"
                            f"{business_answer}\n"
                            "If asked about refunds, answer from this knowledge."
                        ),
                    },
                    {"role": "user", "content": "企业年度套餐退款应该找谁处理？SLA 是多久？"},
                ],
                "temperature": 0,
                "max_tokens": 200,
            },
        ).json()
        grounded_content = grounded.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.record(
            "llm.after_knowledge",
            "ok",
            {
                "mentions_finance_ops": "Finance" in grounded_content or "finance" in grounded_content,
                "mentions_14_days": "14" in grounded_content,
                "content": grounded_content[:500],
            },
        )
        if "14" not in grounded_content or ("Finance" not in grounded_content and "finance" not in grounded_content):
            raise RuntimeError("grounded LLM answer did not reflect deposited company knowledge")

        self.record("business_loop", "passed", {"marker": marker, "job_id": job_id, "knowledge_id": kb_id})
        return 0


def main() -> int:
    harness = Harness()
    try:
        return harness.run()
    except Exception as exc:
        harness.record("business_loop", "failed", {"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
