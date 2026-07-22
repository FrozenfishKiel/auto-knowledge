from __future__ import annotations

import json

from pydantic import ValidationError

from open_webui.utils.auto_knowledge.types import ChatSegment, ExtractedKnowledge


class CandidateExtractionError(ValueError):
    pass


def _extract_json_object(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise CandidateExtractionError("Extractor output is not valid JSON")
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise CandidateExtractionError("Extractor output is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise CandidateExtractionError("Extractor output must be a JSON object")
    return parsed


def parse_extraction_response(raw: str, source_segments: list[ChatSegment]) -> ExtractedKnowledge:
    payload = _extract_json_object(raw)

    source_chat_ids = sorted({segment.chat_id for segment in source_segments})
    source_message_ids: list[str] = []
    for segment in source_segments:
        source_message_ids.extend([segment.user_message_id, segment.assistant_message_id])

    payload.setdefault("source_chat_ids", source_chat_ids)
    payload.setdefault("source_message_ids", source_message_ids)

    try:
        candidate = ExtractedKnowledge.model_validate(payload)
    except ValidationError as exc:
        raise CandidateExtractionError("Extractor output is missing required knowledge fields") from exc

    if not candidate.question.strip() or not candidate.answer.strip():
        raise CandidateExtractionError("Extractor output has empty question or answer")
    if not candidate.source_chat_ids or not candidate.source_message_ids:
        raise CandidateExtractionError("Extractor output has no source references")
    if candidate.confidence < 0 or candidate.confidence > 1:
        raise CandidateExtractionError("Extractor confidence must be between 0 and 1")

    return candidate

