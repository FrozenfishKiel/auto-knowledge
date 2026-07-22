from __future__ import annotations

import logging
import time
import asyncio
from typing import Any

from fastapi import Request
from starlette.datastructures import Headers

from open_webui.internal.db import get_async_db
from open_webui.events import EVENTS, publish_event
from open_webui.models.auto_knowledge import (
    AutoKnowledgeCandidateModel,
    AutoKnowledgeCandidates,
    AutoKnowledgeJobModel,
    AutoKnowledgeJobs,
    AutoKnowledgeRuns,
    RUN_STATUS_FAILED,
    RUN_STATUS_PARTIAL_SUCCESS,
    RUN_STATUS_SUCCESS,
)
from open_webui.models.config import Config
from open_webui.models.users import Users
from open_webui.utils.auto_knowledge.collector import collect_segments_from_chat_messages
from open_webui.utils.auto_knowledge.extractor import parse_extraction_response
from open_webui.utils.auto_knowledge.prompts import build_extraction_prompt
from open_webui.utils.auto_knowledge.runner import run_extraction_pipeline
from open_webui.utils.auto_knowledge.schedules import resolve_window_ns
from open_webui.utils.auto_knowledge.types import ChatSegment, ExtractedKnowledge
from open_webui.utils.automations import next_run_ns, validate_rrule
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.models import get_all_models

log = logging.getLogger(__name__)


def clamp_extraction_concurrency(value: Any, default: int = 8, maximum: int = 32) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def determine_run_status(result, inserted_count: int) -> str:
    if result.cleaned_count > 0 and result.failed_count >= result.cleaned_count and inserted_count == 0:
        return RUN_STATUS_FAILED
    if result.failed_count > 0:
        return RUN_STATUS_PARTIAL_SUCCESS
    return RUN_STATUS_SUCCESS


def get_global_extraction_semaphore(app, limit: int = 32) -> asyncio.Semaphore:
    limit = clamp_extraction_concurrency(limit, default=32, maximum=128)
    state = getattr(app, 'state', None)
    if state is None:
        return asyncio.Semaphore(limit)
    current_limit = getattr(state, 'AUTO_KNOWLEDGE_EXTRACTION_GLOBAL_LIMIT', None)
    semaphore = getattr(state, 'AUTO_KNOWLEDGE_EXTRACTION_GLOBAL_SEMAPHORE', None)
    if semaphore is None or current_limit != limit:
        semaphore = asyncio.Semaphore(limit)
        state.AUTO_KNOWLEDGE_EXTRACTION_GLOBAL_SEMAPHORE = semaphore
        state.AUTO_KNOWLEDGE_EXTRACTION_GLOBAL_LIMIT = limit
    return semaphore


def compute_next_run_at(schedule: dict) -> int | None:
    rrule = schedule.get('rrule')
    if not rrule:
        return None
    tz = schedule.get('timezone')
    validate_rrule(rrule, tz)
    return next_run_ns(rrule, tz)


def safe_compute_next_run_at(schedule: dict) -> int | None:
    try:
        return compute_next_run_at(schedule)
    except Exception:
        log.exception('Failed to compute next Auto Knowledge run')
        return None


def models_to_extracted(candidates: list[AutoKnowledgeCandidateModel]) -> list[ExtractedKnowledge]:
    return [
        ExtractedKnowledge(
            question=item.question,
            answer=item.answer,
            category=item.category or '',
            tags=item.tags or [],
            source_chat_ids=[],
            source_message_ids=[],
            confidence=item.confidence / 100,
            risk_level=item.risk_level,
            metadata=item.meta or {},
        )
        for item in candidates
    ]


def _build_internal_request(app) -> Request:
    scope = {
        'type': 'http',
        'asgi': {'version': '3.0', 'spec_version': '2.0'},
        'method': 'POST',
        'path': '/api/v1/auto-knowledge/internal',
        'query_string': b'',
        'headers': Headers({}).raw,
        'client': ('127.0.0.1', 0),
        'server': ('127.0.0.1', 80),
        'scheme': 'http',
        'app': app,
    }
    request = Request(scope)
    request.state.enable_api_keys = False
    request.state.token = None
    return request


async def ensure_model_registry(request: Request, model_id: str, user: Any) -> None:
    models = getattr(request.app.state, 'MODELS', {}) or {}
    if model_id not in models:
        await get_all_models(request, user=user)


class OpenWebUIExtractor:
    def __init__(self, app, model_id: str, user: Any, global_concurrency: int = 32):
        self.app = app
        self.model_id = model_id
        self.user = user
        self.global_concurrency = global_concurrency

    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        semaphore = get_global_extraction_semaphore(self.app, self.global_concurrency)
        async with semaphore:
            request = _build_internal_request(self.app)
            await ensure_model_registry(request, self.model_id, self.user)
            response = await generate_chat_completion(
                request,
                form_data={
                    'model': self.model_id,
                    'messages': [{'role': 'user', 'content': build_extraction_prompt(segment)}],
                    'stream': False,
                    'temperature': 0,
                    'response_format': {'type': 'json_object'},
                },
                user=self.user,
            )
        content = _response_content(response)
        candidate = parse_extraction_response(content, [segment])
        candidate.metadata = {
            **candidate.metadata,
            'user_id': segment.user_id,
            'source_roles': ['user', 'assistant'],
            'model_id': segment.model_id,
        }
        return candidate


def _response_content(response: Any) -> str:
    if isinstance(response, dict):
        return response.get('choices', [{}])[0].get('message', {}).get('content', '')
    if hasattr(response, 'body'):
        return response.body.decode('utf-8')
    return str(response)


async def execute_auto_knowledge_job(app, job: AutoKnowledgeJobModel) -> None:
    run = await AutoKnowledgeRuns.insert(job.id)
    now_ns = int(time.time_ns())
    try:
        user = await Users.get_user_by_id(job.user_id)
        if not user or user.role != 'admin':
            raise RuntimeError('Job owner is missing or no longer an admin')

        model_id = job.extractor.get('model_id')
        if not model_id:
            raise RuntimeError('Extractor model_id is required')

        start_at, end_at = resolve_window_ns(job, now_ns)
        source_filter = job.source_filter or {}
        segments = await collect_segments_from_chat_messages(
            start_at=start_at,
            end_at=end_at,
            user_ids=source_filter.get('user_ids'),
            group_ids=source_filter.get('group_ids'),
            model_ids=source_filter.get('model_ids'),
            limit=int(source_filter.get('limit') or 1000),
        )
        existing = models_to_extracted(await AutoKnowledgeCandidates.get_existing_for_target(job.target_knowledge_id))
        extraction_concurrency = clamp_extraction_concurrency(job.extractor.get('concurrency'), default=8, maximum=32)
        global_extraction_concurrency = clamp_extraction_concurrency(
            job.extractor.get('global_concurrency'),
            default=32,
            maximum=128,
        )
        result = await run_extraction_pipeline(
            segments,
            OpenWebUIExtractor(app, model_id, user, global_concurrency=global_extraction_concurrency),
            existing,
            extraction_concurrency=extraction_concurrency,
        )
        inserted = await AutoKnowledgeCandidates.insert_many(
            job.id,
            run.id,
            job.target_knowledge_id,
            result.candidates,
        )
        status = determine_run_status(result, len(inserted))
        await AutoKnowledgeRuns.update_by_id(
            run.id,
            {
                'status': status,
                'finished_at': int(time.time_ns()),
                'input_count': result.input_count,
                'cleaned_count': result.cleaned_count,
                'generated_count': len(inserted),
                'duplicate_count': result.duplicate_count,
                'failed_count': result.failed_count,
                'error': '\n'.join(result.errors[:5]) if result.errors else None,
                'meta': {'window': {'start_at': start_at, 'end_at': end_at}},
            },
        )
        await publish_event(
            app,
            EVENTS.AUTO_KNOWLEDGE_JOB_RUN_COMPLETED,
            actor=user,
            subject_id=job.id,
            subject_type='auto_knowledge.job',
            source='scheduler',
            data={
                'run_id': run.id,
                'status': status,
                'input_count': result.input_count,
                'generated_count': len(inserted),
                'duplicate_count': result.duplicate_count,
                'failed_count': result.failed_count,
            },
        )
    except Exception as exc:
        log.exception('Auto Knowledge job %s failed', job.id)
        await AutoKnowledgeRuns.update_by_id(
            run.id,
            {
                'status': RUN_STATUS_FAILED,
                'finished_at': int(time.time_ns()),
                'error': str(exc)[:4000],
            },
        )
        await publish_event(
            app,
            EVENTS.AUTO_KNOWLEDGE_JOB_RUN_FAILED,
            subject_id=job.id,
            subject_type='auto_knowledge.job',
            source='scheduler',
            data={'run_id': run.id, 'error': str(exc)[:1000]},
        )
    finally:
        await AutoKnowledgeJobs.mark_finished(job.id, safe_compute_next_run_at(job.schedule))


async def claim_and_execute_due_jobs(app, limit: int = 3) -> int:
    if not await Config.get('auto_knowledge.enable', True):
        return 0
    async with get_async_db() as db:
        jobs = await AutoKnowledgeJobs.claim_due(int(time.time_ns()), limit=limit, db=db)
    for job in jobs:
        import asyncio

        asyncio.create_task(execute_auto_knowledge_job(app, job))
    return len(jobs)
