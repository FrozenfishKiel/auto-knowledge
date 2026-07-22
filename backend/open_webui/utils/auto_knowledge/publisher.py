from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from fastapi import Request
    from open_webui.models.auto_knowledge import AutoKnowledgeCandidateModel


def render_candidate_markdown(candidate: 'AutoKnowledgeCandidateModel') -> str:
    tags = ", ".join(candidate.tags or [])
    parts = [
        f"# {candidate.question.strip()}",
        "",
        candidate.answer.strip(),
        "",
        "## Metadata",
        f"- Category: {candidate.category or 'Uncategorized'}",
        f"- Tags: {tags or 'None'}",
        f"- Confidence: {candidate.confidence}%",
        f"- Risk level: {candidate.risk_level}",
        f"- Auto Knowledge candidate: {candidate.id}",
    ]
    return "\n".join(parts).strip() + "\n"


async def publish_candidate_to_knowledge(
    candidate: 'AutoKnowledgeCandidateModel',
    user: Any,
    request: 'Request | None' = None,
) -> 'AutoKnowledgeCandidateModel':
    from open_webui.models.auto_knowledge import AutoKnowledgeCandidates
    from open_webui.models.auto_knowledge import AutoKnowledgeRuns
    from open_webui.models.files import FileForm, Files
    from open_webui.models.knowledge import Knowledges
    from open_webui.internal.db import get_async_db
    from open_webui.routers.retrieval import ProcessFileForm, process_file
    from open_webui.utils.misc import calculate_sha256_string

    if candidate.status == 'published':
        return candidate
    if candidate.status != 'approved':
        raise ValueError('Candidate must be approved before publish')

    content = render_candidate_markdown(candidate)
    filename = f"auto-knowledge-{candidate.id}.md"
    file_id = str(uuid4())

    try:
        file = await Files.insert_new_file(
            user.id,
            FileForm(
                id=file_id,
                hash=calculate_sha256_string(content),
                filename=filename,
                path='',
                data={'content': content, 'status': 'uploaded'},
                meta={
                    'name': filename,
                    'content_type': 'text/markdown',
                    'size': len(content.encode('utf-8')),
                    'source': 'auto_knowledge',
                    'auto_knowledge_candidate_id': candidate.id,
                    'created_at': int(time.time()),
                },
            ),
        )
        if not file:
            raise RuntimeError('Failed to create knowledge file')

        async with get_async_db() as db:
            if request is not None:
                await process_file(
                    request,
                    ProcessFileForm(file_id=file.id, content=content, collection_name=candidate.target_knowledge_id),
                    user=user,
                    db=db,
                )

            knowledge_file = await Knowledges.add_file_to_knowledge_by_id(
                candidate.target_knowledge_id,
                file.id,
                user.id,
                db=db,
            )
        if not knowledge_file:
            raise RuntimeError('Failed to attach file to knowledge base')

        updated = await AutoKnowledgeCandidates.update_by_id(
            candidate.id,
            {
                'published_file_id': file.id,
                'status': 'published',
            },
        )
        if not updated:
            raise RuntimeError('Published candidate disappeared before status update')
        await AutoKnowledgeRuns.increment_published_count(candidate.run_id)
        return updated
    except Exception as exc:
        updated = await AutoKnowledgeCandidates.update_by_id(
            candidate.id,
            {
                'status': 'publish_failed',
                'meta': {**(candidate.meta or {}), 'publish_error': str(exc)[:1000]},
            },
        )
        if updated:
            return updated
        raise
