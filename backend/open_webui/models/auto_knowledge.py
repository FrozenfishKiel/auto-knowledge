from __future__ import annotations

import time
from typing import Optional
from uuid import uuid4

from open_webui.internal.db import Base, get_async_db_context
from open_webui.utils.auto_knowledge.cleaner import mask_sensitive_text
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import JSON, BigInteger, Boolean, Column, ForeignKey, Index, Text, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

JOB_STATUS_ACTIVE = "active"
JOB_STATUS_PAUSED = "paused"

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_PARTIAL_SUCCESS = "partial_success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

CANDIDATE_STATUS_PENDING = "pending_review"
CANDIDATE_STATUS_APPROVED = "approved"
CANDIDATE_STATUS_REJECTED = "rejected"
CANDIDATE_STATUS_PUBLISHED = "published"
CANDIDATE_STATUS_PUBLISH_FAILED = "publish_failed"


class AutoKnowledgeJob(Base):
    __tablename__ = "auto_knowledge_job"

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    target_knowledge_id = Column(Text, nullable=False)
    source_filter = Column(JSON, nullable=False)
    schedule = Column(JSON, nullable=False)
    extractor = Column(JSON, nullable=False)
    review_policy = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_running = Column(Boolean, nullable=False, default=False)
    last_run_at = Column(BigInteger, nullable=True)
    next_run_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_auto_knowledge_job_next_run", "next_run_at"),
        Index("ix_auto_knowledge_job_active_running", "is_active", "is_running"),
        Index("ix_auto_knowledge_job_target_knowledge", "target_knowledge_id"),
    )


class AutoKnowledgeRun(Base):
    __tablename__ = "auto_knowledge_run"

    id = Column(Text, primary_key=True)
    job_id = Column(Text, ForeignKey("auto_knowledge_job.id", ondelete="CASCADE"), nullable=False)
    status = Column(Text, nullable=False)
    started_at = Column(BigInteger, nullable=False)
    finished_at = Column(BigInteger, nullable=True)
    input_count = Column(BigInteger, nullable=False, default=0)
    cleaned_count = Column(BigInteger, nullable=False, default=0)
    generated_count = Column(BigInteger, nullable=False, default=0)
    duplicate_count = Column(BigInteger, nullable=False, default=0)
    failed_count = Column(BigInteger, nullable=False, default=0)
    published_count = Column(BigInteger, nullable=False, default=0)
    error = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_auto_knowledge_run_job_created", "job_id", "created_at"),
        Index("ix_auto_knowledge_run_status", "status"),
    )


class AutoKnowledgeCandidate(Base):
    __tablename__ = "auto_knowledge_candidate"

    id = Column(Text, primary_key=True)
    job_id = Column(Text, ForeignKey("auto_knowledge_job.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(Text, ForeignKey("auto_knowledge_run.id", ondelete="CASCADE"), nullable=False)
    target_knowledge_id = Column(Text, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)
    confidence = Column(BigInteger, nullable=False)
    risk_level = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default=CANDIDATE_STATUS_PENDING)
    duplicate_of = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    published_file_id = Column(Text, nullable=True)
    reviewed_by = Column(Text, nullable=True)
    reviewed_at = Column(BigInteger, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_auto_knowledge_candidate_job_status", "job_id", "status"),
        Index("ix_auto_knowledge_candidate_target_status", "target_knowledge_id", "status"),
        Index("ix_auto_knowledge_candidate_run", "run_id"),
    )


class AutoKnowledgeSource(Base):
    __tablename__ = "auto_knowledge_source"

    id = Column(Text, primary_key=True)
    candidate_id = Column(Text, ForeignKey("auto_knowledge_candidate.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(Text, nullable=False)
    message_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_auto_knowledge_source_candidate", "candidate_id"),
        Index("ix_auto_knowledge_source_chat", "chat_id"),
    )


class AutoKnowledgeJobModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    target_knowledge_id: str
    source_filter: dict
    schedule: dict
    extractor: dict
    review_policy: dict
    is_active: bool
    is_running: bool
    last_run_at: Optional[int] = None
    next_run_at: Optional[int] = None
    created_at: int
    updated_at: int


class AutoKnowledgeRunModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    status: str
    started_at: int
    finished_at: Optional[int] = None
    input_count: int = 0
    cleaned_count: int = 0
    generated_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    published_count: int = 0
    error: Optional[str] = None
    meta: Optional[dict] = None
    created_at: int
    updated_at: int

    @computed_field
    @property
    def duration_ns(self) -> Optional[int]:
        if self.finished_at is None:
            return None
        return max(0, self.finished_at - self.started_at)

    @computed_field
    @property
    def duration_ms(self) -> Optional[int]:
        if self.duration_ns is None:
            return None
        return self.duration_ns // 1_000_000


class AutoKnowledgeCandidateModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    run_id: str
    target_knowledge_id: str
    question: str
    answer: str
    category: Optional[str] = None
    tags: Optional[list[str]] = Field(default_factory=list)
    confidence: int
    risk_level: str
    status: str
    duplicate_of: Optional[str] = None
    rejection_reason: Optional[str] = None
    published_file_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[int] = None
    meta: Optional[dict] = None
    created_at: int
    updated_at: int


class AutoKnowledgeSourceModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    chat_id: str
    message_id: str
    user_id: str
    role: str
    created_at: int


class AutoKnowledgeSourcePreviewModel(AutoKnowledgeSourceModel):
    content: Optional[str] = None
    model_id: Optional[str] = None


class AutoKnowledgeJobForm(BaseModel):
    name: str
    description: Optional[str] = None
    target_knowledge_id: str
    source_filter: dict
    schedule: dict
    extractor: dict = Field(default_factory=dict)
    review_policy: dict = Field(default_factory=lambda: {"mode": "manual"})
    is_active: bool = True


class AutoKnowledgeCandidateReviewForm(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    rejection_reason: Optional[str] = None


class AutoKnowledgeJobListResponse(BaseModel):
    items: list[AutoKnowledgeJobModel]
    total: int


class AutoKnowledgeCandidateListResponse(BaseModel):
    items: list[AutoKnowledgeCandidateModel]
    total: int


class AutoKnowledgeCandidateDetailResponse(AutoKnowledgeCandidateModel):
    sources: list[AutoKnowledgeSourcePreviewModel] = Field(default_factory=list)


def sanitize_source_preview_content(content: Optional[str]) -> Optional[str]:
    if content is None:
        return None
    return mask_sensitive_text(content)


class AutoKnowledgeJobTable:
    async def insert(
        self,
        user_id: str,
        form: AutoKnowledgeJobForm,
        next_run_at: Optional[int],
        db: Optional[AsyncSession] = None,
    ) -> AutoKnowledgeJobModel:
        async with get_async_db_context(db) as db:
            now = int(time.time_ns())
            row = AutoKnowledgeJob(
                id=str(uuid4()),
                user_id=user_id,
                name=form.name,
                description=form.description,
                target_knowledge_id=form.target_knowledge_id,
                source_filter=form.source_filter,
                schedule=form.schedule,
                extractor=form.extractor,
                review_policy=form.review_policy,
                is_active=form.is_active,
                is_running=False,
                next_run_at=next_run_at,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeJobModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[AutoKnowledgeJobModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeJob, id)
            return AutoKnowledgeJobModel.model_validate(row) if row else None

    async def search(
        self,
        skip: int = 0,
        limit: int = 30,
        status: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> AutoKnowledgeJobListResponse:
        async with get_async_db_context(db) as db:
            stmt = select(AutoKnowledgeJob)
            if status == JOB_STATUS_ACTIVE:
                stmt = stmt.where(AutoKnowledgeJob.is_active == True)
            elif status == JOB_STATUS_PAUSED:
                stmt = stmt.where(AutoKnowledgeJob.is_active == False)

            total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
            result = await db.execute(
                stmt.order_by(AutoKnowledgeJob.updated_at.desc()).offset(skip).limit(limit)
            )
            return AutoKnowledgeJobListResponse(
                items=[AutoKnowledgeJobModel.model_validate(row) for row in result.scalars().all()],
                total=total,
            )

    async def update_by_id(
        self,
        id: str,
        form: AutoKnowledgeJobForm,
        next_run_at: Optional[int],
        db: Optional[AsyncSession] = None,
    ) -> Optional[AutoKnowledgeJobModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeJob, id)
            if not row:
                return None
            row.name = form.name
            row.description = form.description
            row.target_knowledge_id = form.target_knowledge_id
            row.source_filter = form.source_filter
            row.schedule = form.schedule
            row.extractor = form.extractor
            row.review_policy = form.review_policy
            row.is_active = form.is_active
            row.next_run_at = next_run_at
            row.updated_at = int(time.time_ns())
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeJobModel.model_validate(row)

    async def delete_by_id(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeJob, id)
            if not row:
                return False
            await db.delete(row)
            await db.commit()
            return True

    async def claim_due(
        self, now_ns: int, limit: int = 5, db: Optional[AsyncSession] = None
    ) -> list[AutoKnowledgeJobModel]:
        async with get_async_db_context(db) as db:
            stmt = (
                select(AutoKnowledgeJob)
                .where(
                    AutoKnowledgeJob.is_active == True,
                    AutoKnowledgeJob.is_running == False,
                    AutoKnowledgeJob.next_run_at.isnot(None),
                    AutoKnowledgeJob.next_run_at <= now_ns,
                )
                .order_by(AutoKnowledgeJob.next_run_at)
                .limit(limit)
            )
            bind = await db.connection()
            if bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)

            rows = (await db.execute(stmt)).scalars().all()
            for row in rows:
                row.is_running = True
                row.last_run_at = now_ns
                row.updated_at = now_ns
            await db.commit()
            return [AutoKnowledgeJobModel.model_validate(row) for row in rows]

    async def mark_finished(
        self,
        id: str,
        next_run_at: Optional[int],
        db: Optional[AsyncSession] = None,
    ) -> Optional[AutoKnowledgeJobModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeJob, id)
            if not row:
                return None
            row.is_running = False
            row.next_run_at = next_run_at
            row.updated_at = int(time.time_ns())
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeJobModel.model_validate(row)

    async def mark_running(self, id: str, db: Optional[AsyncSession] = None) -> Optional[AutoKnowledgeJobModel]:
        async with get_async_db_context(db) as db:
            now = int(time.time_ns())
            result = await db.execute(
                update(AutoKnowledgeJob)
                .where(AutoKnowledgeJob.id == id, AutoKnowledgeJob.is_running == False)
                .values(is_running=True, last_run_at=now, updated_at=now)
            )
            await db.commit()
            if result.rowcount != 1:
                return None
            row = await db.get(AutoKnowledgeJob, id)
            if not row:
                return None
            await db.refresh(row)
            return AutoKnowledgeJobModel.model_validate(row)


class AutoKnowledgeRunTable:
    async def insert(
        self, job_id: str, status: str = RUN_STATUS_RUNNING, db: Optional[AsyncSession] = None
    ) -> AutoKnowledgeRunModel:
        async with get_async_db_context(db) as db:
            now = int(time.time_ns())
            row = AutoKnowledgeRun(
                id=str(uuid4()),
                job_id=job_id,
                status=status,
                started_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeRunModel.model_validate(row)

    async def update_by_id(self, id: str, data: dict, db: Optional[AsyncSession] = None) -> Optional[AutoKnowledgeRunModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeRun, id)
            if not row:
                return None
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            row.updated_at = int(time.time_ns())
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeRunModel.model_validate(row)

    async def get_by_job(
        self, job_id: str, skip: int = 0, limit: int = 50, db: Optional[AsyncSession] = None
    ) -> list[AutoKnowledgeRunModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(AutoKnowledgeRun)
                .where(AutoKnowledgeRun.job_id == job_id)
                .order_by(AutoKnowledgeRun.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return [AutoKnowledgeRunModel.model_validate(row) for row in result.scalars().all()]

    async def increment_published_count(
        self, id: str, db: Optional[AsyncSession] = None
    ) -> Optional[AutoKnowledgeRunModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeRun, id)
            if not row:
                return None
            row.published_count = (row.published_count or 0) + 1
            row.updated_at = int(time.time_ns())
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeRunModel.model_validate(row)


class AutoKnowledgeCandidateTable:
    async def insert_many(
        self,
        job_id: str,
        run_id: str,
        target_knowledge_id: str,
        candidates: list,
        db: Optional[AsyncSession] = None,
    ) -> list[AutoKnowledgeCandidateModel]:
        async with get_async_db_context(db) as db:
            now = int(time.time_ns())
            rows = []
            source_rows = []
            for candidate in candidates:
                candidate_id = str(uuid4())
                rows.append(
                    AutoKnowledgeCandidate(
                        id=candidate_id,
                        job_id=job_id,
                        run_id=run_id,
                        target_knowledge_id=target_knowledge_id,
                        question=candidate.question,
                        answer=candidate.answer,
                        category=candidate.category,
                        tags=candidate.tags,
                        confidence=int(candidate.confidence * 100),
                        risk_level=candidate.risk_level,
                        status=CANDIDATE_STATUS_PENDING,
                        meta=candidate.metadata,
                        created_at=now,
                        updated_at=now,
                    )
                )
                source_chat_id = candidate.source_chat_ids[0] if candidate.source_chat_ids else ''
                source_roles = candidate.metadata.get('source_roles', [])
                for idx, message_id in enumerate(candidate.source_message_ids):
                    source_rows.append(
                        AutoKnowledgeSource(
                            id=str(uuid4()),
                            candidate_id=candidate_id,
                            chat_id=source_chat_id,
                            message_id=message_id,
                            user_id=candidate.metadata.get('user_id', ''),
                            role=source_roles[idx] if idx < len(source_roles) else '',
                            created_at=now,
                        )
                    )
            db.add_all(rows)
            db.add_all(source_rows)
            await db.commit()
            for row in rows:
                await db.refresh(row)
            return [AutoKnowledgeCandidateModel.model_validate(row) for row in rows]

    async def search(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 30,
        db: Optional[AsyncSession] = None,
    ) -> AutoKnowledgeCandidateListResponse:
        async with get_async_db_context(db) as db:
            stmt = select(AutoKnowledgeCandidate)
            if job_id:
                stmt = stmt.where(AutoKnowledgeCandidate.job_id == job_id)
            if status:
                stmt = stmt.where(AutoKnowledgeCandidate.status == status)

            total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
            result = await db.execute(
                stmt.order_by(AutoKnowledgeCandidate.created_at.desc()).offset(skip).limit(limit)
            )
            return AutoKnowledgeCandidateListResponse(
                items=[AutoKnowledgeCandidateModel.model_validate(row) for row in result.scalars().all()],
                total=total,
            )

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[AutoKnowledgeCandidateModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeCandidate, id)
            return AutoKnowledgeCandidateModel.model_validate(row) if row else None

    async def get_sources_by_candidate_id(
        self,
        candidate_id: str,
        db: Optional[AsyncSession] = None,
    ) -> list[AutoKnowledgeSourceModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(AutoKnowledgeSource)
                .where(AutoKnowledgeSource.candidate_id == candidate_id)
                .order_by(AutoKnowledgeSource.created_at.asc())
            )
            return [AutoKnowledgeSourceModel.model_validate(row) for row in result.scalars().all()]

    async def get_detail_by_id(
        self,
        id: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[AutoKnowledgeCandidateDetailResponse]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeCandidate, id)
            if not row:
                return None
            result = await db.execute(
                select(AutoKnowledgeSource)
                .where(AutoKnowledgeSource.candidate_id == id)
                .order_by(AutoKnowledgeSource.created_at.asc())
            )
            sources = result.scalars().all()
            message_ids = {
                source.message_id
                for source in sources
                if source.message_id
            }
            message_ids.update(
                f'{source.chat_id}-{source.message_id}'
                for source in sources
                if source.chat_id and source.message_id and not source.message_id.startswith(f'{source.chat_id}-')
            )
            messages_by_id = {}
            if message_ids:
                from open_webui.models.chat_messages import ChatMessage
                from open_webui.utils.auto_knowledge.collector import content_to_text

                messages = (
                    await db.execute(
                        select(ChatMessage).where(
                            or_(
                                ChatMessage.id.in_(message_ids),
                                ChatMessage.parent_id.in_(message_ids),
                            )
                        )
                    )
                ).scalars().all()
                for message in messages:
                    messages_by_id[message.id] = message
                    stripped_id = message.id.removeprefix(f'{message.chat_id}-')
                    messages_by_id[stripped_id] = message
            return AutoKnowledgeCandidateDetailResponse(
                **AutoKnowledgeCandidateModel.model_validate(row).model_dump(),
                sources=[
                    AutoKnowledgeSourcePreviewModel(
                        **AutoKnowledgeSourceModel.model_validate(source).model_dump(),
                        content=sanitize_source_preview_content(
                            content_to_text(getattr(messages_by_id.get(source.message_id), 'content', None))
                        )
                        if message_ids
                        else None,
                        model_id=getattr(messages_by_id.get(source.message_id), 'model_id', None)
                        if message_ids
                        else None,
                    )
                    for source in sources
                ],
            )

    async def get_existing_for_target(
        self,
        target_knowledge_id: str,
        db: Optional[AsyncSession] = None,
    ) -> list[AutoKnowledgeCandidateModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(AutoKnowledgeCandidate).where(
                    AutoKnowledgeCandidate.target_knowledge_id == target_knowledge_id,
                    AutoKnowledgeCandidate.status.in_(
                        [
                            CANDIDATE_STATUS_PENDING,
                            CANDIDATE_STATUS_APPROVED,
                            CANDIDATE_STATUS_PUBLISHED,
                        ]
                    ),
                )
            )
            return [AutoKnowledgeCandidateModel.model_validate(row) for row in result.scalars().all()]

    async def update_by_id(
        self, id: str, data: dict, db: Optional[AsyncSession] = None
    ) -> Optional[AutoKnowledgeCandidateModel]:
        async with get_async_db_context(db) as db:
            row = await db.get(AutoKnowledgeCandidate, id)
            if not row:
                return None
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            row.updated_at = int(time.time_ns())
            await db.commit()
            await db.refresh(row)
            return AutoKnowledgeCandidateModel.model_validate(row)

    async def mark_reviewed(
        self,
        id: str,
        status: str,
        reviewed_by: str,
        form: AutoKnowledgeCandidateReviewForm | None = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[AutoKnowledgeCandidateModel]:
        data = {
            'status': status,
            'reviewed_by': reviewed_by,
            'reviewed_at': int(time.time_ns()),
        }
        if form:
            for key in ['question', 'answer', 'category', 'tags', 'rejection_reason']:
                value = getattr(form, key)
                if value is not None:
                    data[key] = value
        return await self.update_by_id(id, data, db=db)


AutoKnowledgeJobs = AutoKnowledgeJobTable()
AutoKnowledgeRuns = AutoKnowledgeRunTable()
AutoKnowledgeCandidates = AutoKnowledgeCandidateTable()
