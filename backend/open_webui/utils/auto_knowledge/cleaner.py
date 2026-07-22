from __future__ import annotations

import re

from open_webui.utils.auto_knowledge.types import ChatSegment

MIN_TEXT_LENGTH = 8

PRIVATE_PATTERNS = [
    ("API_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"\b1[3-9]\d{9}\b")),
    ("QQ", re.compile(r"(?:QQ|qq)[:：\s-]*[1-9]\d{4,11}\b")),
    ("WECHAT", re.compile(r"(?:微信|wechat|WeChat)[:：\s-]*[A-Za-z][-_A-Za-z0-9]{5,19}\b")),
    ("ORDER_ID", re.compile(r"\b(?:ORD|ORDER|订单)[-_：:]?[A-Za-z0-9-]{6,}\b", re.IGNORECASE)),
    ("ID_CARD", re.compile(r"\b\d{17}[\dXx]\b")),
]

LOW_VALUE_TEXT = {
    "你好",
    "您好",
    "谢谢",
    "好的",
    "收到",
    "ok",
    "hi",
    "hello",
}


def mask_sensitive_text(text: str) -> str:
    masked = text or ""
    for label, pattern in PRIVATE_PATTERNS:
        masked = pattern.sub(f"[{label}]", masked)
    return masked


def _is_low_value(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in LOW_VALUE_TEXT or len(normalized) < MIN_TEXT_LENGTH


def clean_segments(segments: list[ChatSegment]) -> list[ChatSegment]:
    cleaned: list[ChatSegment] = []
    for segment in segments:
        if segment.error:
            continue
        if _is_low_value(segment.user_text) or _is_low_value(segment.assistant_text):
            continue

        cleaned.append(
            segment.model_copy(
                update={
                    "user_text": mask_sensitive_text(segment.user_text),
                    "assistant_text": mask_sensitive_text(segment.assistant_text),
                }
            )
        )
    return cleaned
