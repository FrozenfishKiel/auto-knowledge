from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatSegment(BaseModel):
    chat_id: str
    user_id: str
    user_message_id: str
    assistant_message_id: str
    user_text: str
    assistant_text: str
    created_at: int
    model_id: str | None = None
    error: dict | str | None = None


class ExtractedKnowledge(BaseModel):
    question: str
    answer: str
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    source_chat_ids: list[str] = Field(default_factory=list)
    source_message_ids: list[str] = Field(default_factory=list)
    confidence: float
    risk_level: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

