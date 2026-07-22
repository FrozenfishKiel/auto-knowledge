from __future__ import annotations

import re

from open_webui.utils.auto_knowledge.types import ExtractedKnowledge


def normalize_question(question: str) -> str:
    normalized = question.lower().strip()
    normalized = re.sub(r"[\s?？!！。.,，；;：:]+", "", normalized)
    return normalized


def find_duplicate(
    candidate: ExtractedKnowledge,
    existing: list[ExtractedKnowledge],
) -> ExtractedKnowledge | None:
    candidate_key = normalize_question(candidate.question)
    for item in existing:
        if normalize_question(item.question) == candidate_key:
            return item
    return None
