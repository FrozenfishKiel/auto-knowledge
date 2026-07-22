from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.auto_knowledge import (
    AutoKnowledgeCandidateDetailResponse,
    AutoKnowledgeCandidateListResponse,
    AutoKnowledgeCandidateReviewForm,
    AutoKnowledgeCandidates,
    AutoKnowledgeJobForm,
    AutoKnowledgeJobListResponse,
    AutoKnowledgeJobModel,
    AutoKnowledgeJobs,
    AutoKnowledgeRunModel,
    AutoKnowledgeRuns,
    CANDIDATE_STATUS_APPROVED,
    CANDIDATE_STATUS_PUBLISHED,
    CANDIDATE_STATUS_REJECTED,
)
from open_webui.models.knowledge import Knowledges
from open_webui.events import EVENTS, publish_event
from open_webui.utils.auth import get_admin_user
from open_webui.utils.auto_knowledge.publisher import publish_candidate_to_knowledge
from open_webui.utils.auto_knowledge.scheduler import compute_next_run_at, execute_auto_knowledge_job

router = APIRouter()


async def _verify_target_knowledge(id: str, db: AsyncSession):
    knowledge = await Knowledges.get_knowledge_by_id(id, db=db)
    if not knowledge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if (knowledge.meta or {}).get('source') == 'external':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='External knowledge bases are read-only.')
    return knowledge


@router.get('/', response_model=AutoKnowledgeJobListResponse)
async def list_auto_knowledge_jobs(
    status: str | None = None,
    page: int = Query(1, ge=1),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    limit = 30
    return await AutoKnowledgeJobs.search(skip=(page - 1) * limit, limit=limit, status=status, db=db)


@router.post('/create', response_model=AutoKnowledgeJobModel)
async def create_auto_knowledge_job(
    request: Request,
    form_data: AutoKnowledgeJobForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _verify_target_knowledge(form_data.target_knowledge_id, db)
    job = await AutoKnowledgeJobs.insert(user.id, form_data, compute_next_run_at(form_data.schedule), db=db)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_JOB_CREATED,
        actor=user,
        subject_id=job.id,
        subject_type='auto_knowledge.job',
        data={'target_knowledge_id': job.target_knowledge_id},
    )
    return job


@router.get('/{id}', response_model=AutoKnowledgeJobModel)
async def get_auto_knowledge_job(
    id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    job = await AutoKnowledgeJobs.get_by_id(id, db=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return job


@router.post('/{id}/update', response_model=AutoKnowledgeJobModel)
async def update_auto_knowledge_job(
    request: Request,
    id: str,
    form_data: AutoKnowledgeJobForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _verify_target_knowledge(form_data.target_knowledge_id, db)
    job = await AutoKnowledgeJobs.update_by_id(id, form_data, compute_next_run_at(form_data.schedule), db=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_JOB_UPDATED,
        actor=user,
        subject_id=job.id,
        subject_type='auto_knowledge.job',
        data={'target_knowledge_id': job.target_knowledge_id, 'is_active': job.is_active},
    )
    return job


@router.delete('/{id}/delete')
async def delete_auto_knowledge_job(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    deleted = await AutoKnowledgeJobs.delete_by_id(id, db=db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_JOB_DELETED,
        actor=user,
        subject_id=id,
        subject_type='auto_knowledge.job',
    )
    return {'status': True}


@router.post('/{id}/run')
async def run_auto_knowledge_job_now(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    job = await AutoKnowledgeJobs.get_by_id(id, db=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    claimed = await AutoKnowledgeJobs.mark_running(id, db=db)
    if not claimed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Auto Knowledge job is already running.')
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_JOB_RUN_REQUESTED,
        actor=user,
        subject_id=id,
        subject_type='auto_knowledge.job',
    )
    asyncio.create_task(execute_auto_knowledge_job(request.app, claimed))
    return {'status': True}


@router.get('/{id}/runs', response_model=list[AutoKnowledgeRunModel])
async def list_auto_knowledge_runs(
    id: str,
    page: int = Query(1, ge=1),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not await AutoKnowledgeJobs.get_by_id(id, db=db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return await AutoKnowledgeRuns.get_by_job(id, skip=(page - 1) * 50, limit=50, db=db)


@router.get('/candidates/list', response_model=AutoKnowledgeCandidateListResponse)
async def list_auto_knowledge_candidates(
    job_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await AutoKnowledgeCandidates.search(
        job_id=job_id,
        status=status,
        skip=(page - 1) * 30,
        limit=30,
        db=db,
    )


@router.get('/candidates/{id}', response_model=AutoKnowledgeCandidateDetailResponse)
async def get_auto_knowledge_candidate(
    id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = await AutoKnowledgeCandidates.get_detail_by_id(id, db=db)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return candidate


@router.post('/candidates/{id}/approve')
async def approve_auto_knowledge_candidate(
    request: Request,
    id: str,
    form_data: AutoKnowledgeCandidateReviewForm,
    publish: bool = Query(False),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = await AutoKnowledgeCandidates.mark_reviewed(
        id,
        CANDIDATE_STATUS_APPROVED,
        reviewed_by=user.id,
        form=form_data,
        db=db,
    )
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_CANDIDATE_APPROVED,
        actor=user,
        subject_id=id,
        subject_type='auto_knowledge.candidate',
        data={'job_id': candidate.job_id, 'run_id': candidate.run_id},
    )
    if publish:
        candidate = await publish_candidate_to_knowledge(candidate, user, request=request)
        await publish_event(
            request,
            EVENTS.AUTO_KNOWLEDGE_CANDIDATE_PUBLISHED,
            actor=user,
            subject_id=id,
            subject_type='auto_knowledge.candidate',
            data={'job_id': candidate.job_id, 'run_id': candidate.run_id, 'published_file_id': candidate.published_file_id},
        )
    return candidate


@router.post('/candidates/{id}/reject')
async def reject_auto_knowledge_candidate(
    request: Request,
    id: str,
    form_data: AutoKnowledgeCandidateReviewForm,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = await AutoKnowledgeCandidates.mark_reviewed(
        id,
        CANDIDATE_STATUS_REJECTED,
        reviewed_by=user.id,
        form=form_data,
        db=db,
    )
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_CANDIDATE_REJECTED,
        actor=user,
        subject_id=id,
        subject_type='auto_knowledge.candidate',
        data={'job_id': candidate.job_id, 'run_id': candidate.run_id},
    )
    return candidate


@router.post('/candidates/{id}/publish')
async def publish_auto_knowledge_candidate(
    request: Request,
    id: str,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = await AutoKnowledgeCandidates.get_by_id(id, db=db)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if candidate.status == CANDIDATE_STATUS_PUBLISHED:
        return candidate
    if candidate.status != CANDIDATE_STATUS_APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Candidate must be approved before publish.')
    candidate = await publish_candidate_to_knowledge(candidate, user, request=request)
    await publish_event(
        request,
        EVENTS.AUTO_KNOWLEDGE_CANDIDATE_PUBLISHED,
        actor=user,
        subject_id=id,
        subject_type='auto_knowledge.candidate',
        data={'job_id': candidate.job_id, 'run_id': candidate.run_id, 'published_file_id': candidate.published_file_id},
    )
    return candidate
