from __future__ import annotations

import asyncio
from typing import Protocol

from pydantic import BaseModel, Field

from open_webui.utils.auto_knowledge.cleaner import clean_segments
from open_webui.utils.auto_knowledge.deduplicator import find_duplicate
from open_webui.utils.auto_knowledge.types import ChatSegment, ExtractedKnowledge


class KnowledgeExtractor(Protocol):
    async def extract(self, segment: ChatSegment) -> ExtractedKnowledge:
        pass


class ExtractionPipelineResult(BaseModel):
    input_count: int = 0
    cleaned_count: int = 0
    generated_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    candidates: list[ExtractedKnowledge] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


async def run_extraction_pipeline(
    segments: list[ChatSegment],
    extractor: KnowledgeExtractor,
    existing_candidates: list[ExtractedKnowledge] | None = None,
    extraction_concurrency: int = 8,
) -> ExtractionPipelineResult:
    existing = list(existing_candidates or [])
    cleaned = clean_segments(segments)
    candidates: list[ExtractedKnowledge] = []
    errors: list[str] = []
    duplicate_count = 0
    concurrency = max(1, min(int(extraction_concurrency or 1), 32))
    semaphore = asyncio.Semaphore(concurrency)

    async def extract_one(segment: ChatSegment) -> ExtractedKnowledge | Exception:
        async with semaphore:
            try:
                return await extractor.extract(segment)
            except Exception as exc:
                return exc

    extracted = await asyncio.gather(*(extract_one(segment) for segment in cleaned))

    for item in extracted:
        if isinstance(item, Exception):
            errors.append(str(item))
            continue
        candidate = item
        try:
            duplicate = find_duplicate(candidate, [*existing, *candidates])
        except Exception as exc:
            errors.append(str(exc))
            continue

        if duplicate:
            duplicate_count += 1
            continue

        candidates.append(candidate)

    return ExtractionPipelineResult(
        input_count=len(segments),
        cleaned_count=len(cleaned),
        generated_count=len(candidates),
        duplicate_count=duplicate_count,
        failed_count=len(errors),
        candidates=candidates,
        errors=errors,
    )
