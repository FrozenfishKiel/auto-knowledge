from __future__ import annotations

from typing import Any

from open_webui.utils.auto_knowledge.types import ChatSegment


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        return text if isinstance(text, str) else ""
    return str(content)


def build_segments_from_messages(messages: list[dict[str, Any]]) -> list[ChatSegment]:
    by_id: dict[str, dict[str, Any]] = {}
    for message in messages:
        if message.get("id"):
            by_id[message["id"]] = message
        alias = _stripped_message_id(message)
        if alias:
            by_id[alias] = message
    segments: list[ChatSegment] = []

    for message in sorted(messages, key=lambda item: item.get("created_at") or 0):
        if message.get("role") != "assistant":
            continue

        parent = by_id.get(message.get("parent_id"))
        if not parent or parent.get("role") != "user":
            continue

        user_text = content_to_text(parent.get("content")).strip()
        assistant_text = content_to_text(message.get("content")).strip()
        if not user_text or not assistant_text:
            continue

        segments.append(
            ChatSegment(
                chat_id=message.get("chat_id") or parent.get("chat_id") or "",
                user_id=parent.get("user_id") or message.get("user_id") or "",
                user_message_id=_source_message_id(parent, message.get("parent_id")),
                assistant_message_id=_source_message_id(message, message.get("parent_id")),
                user_text=user_text,
                assistant_text=assistant_text,
                created_at=message.get("created_at") or parent.get("created_at") or 0,
                model_id=message.get("model_id") or message.get("model"),
                error=message.get("error"),
            )
        )

    return segments


def _stripped_message_id(message: dict[str, Any]) -> str | None:
    chat_id = message.get("chat_id") or ""
    message_id = message.get("id")
    if chat_id and isinstance(message_id, str) and message_id.startswith(f"{chat_id}-"):
        return message_id[len(chat_id) + 1 :]
    return None


def _source_message_id(message: dict[str, Any], parent_ref: str | None) -> str:
    message_id = message.get("id") or ""
    stripped = _stripped_message_id(message)
    chat_id = message.get("chat_id") or ""
    parent_uses_raw_id = bool(parent_ref and chat_id and not parent_ref.startswith(f"{chat_id}-"))
    if stripped and parent_uses_raw_id:
        return stripped
    return message_id


def _row_to_message(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "chat_id": row.chat_id,
        "user_id": row.user_id,
        "role": row.role,
        "parent_id": row.parent_id,
        "content": row.content,
        "model_id": row.model_id,
        "error": row.error,
        "created_at": row.created_at,
    }


async def collect_segments_from_chat_messages(
    start_at: int,
    end_at: int,
    user_ids: list[str] | None = None,
    group_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
    limit: int = 1000,
    db: Any | None = None,
) -> list[ChatSegment]:
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.chat_messages import ChatMessage
    from sqlalchemy import select

    async with get_async_db_context(db) as db:
        resolved_user_ids = await resolve_source_user_ids(user_ids=user_ids, group_ids=group_ids, db=db)
        stmt = select(ChatMessage).where(
            ChatMessage.created_at >= start_at,
            ChatMessage.created_at <= end_at,
        )
        if resolved_user_ids is not None:
            if not resolved_user_ids:
                return []
            stmt = stmt.where(ChatMessage.user_id.in_(resolved_user_ids))
        result = await db.execute(stmt.order_by(ChatMessage.created_at.asc()).limit(limit))
        rows = result.scalars().all()

    segments = build_segments_from_messages([_row_to_message(row) for row in rows])
    if model_ids:
        allowed = set(model_ids)
        segments = [segment for segment in segments if segment.model_id in allowed]
    return segments


async def resolve_source_user_ids(
    user_ids: list[str] | None = None,
    group_ids: list[str] | None = None,
    groups: Any | None = None,
    db: Any | None = None,
) -> list[str] | None:
    selected_user_ids: list[str] = []

    for user_id in user_ids or []:
        if user_id and user_id not in selected_user_ids:
            selected_user_ids.append(user_id)

    if group_ids:
        if groups is None:
            from open_webui.models.groups import Groups

            groups = Groups
        members_by_group = await groups.get_group_user_ids_by_ids(group_ids, db=db)
        for group_id in group_ids:
            for user_id in members_by_group.get(group_id, []):
                if user_id and user_id not in selected_user_ids:
                    selected_user_ids.append(user_id)

    if user_ids or group_ids:
        return selected_user_ids
    return None
