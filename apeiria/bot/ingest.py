"""NoneBot event ingestion for conversation persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apeiria.bot.event_context import build_chat_session_identity_from_event
from apeiria.bot.normalization import (
    build_debug_raw_payload,
    build_normalized_content,
    detect_has_media,
    extract_author_name,
    extract_platform_message_id,
    extract_platform_reply_id,
    resolve_message_kind,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.conversation.models import ChatSessionIdentity, MessageKind


@dataclass(frozen=True)
class IngestedChatEvent:
    """Normalized event data ready for conversation persistence."""

    identity: "ChatSessionIdentity"
    author_id: str
    author_name: str
    text_content: str
    message_kind: "MessageKind"
    directed_to_bot: bool
    mentions_bot: bool
    has_media: bool
    platform_message_id: str | None
    platform_reply_id: str | None
    content: dict[str, Any]
    raw_data: dict[str, Any] | None


def build_ingested_chat_event(
    bot: "Bot",
    event: "Event",
    *,
    persist_raw_data: bool = False,
) -> IngestedChatEvent | None:
    """Convert one runtime event into normalized conversation fields."""

    identity = build_chat_session_identity_from_event(bot, event)
    if identity is None:
        return None

    raw_data = event.model_dump(mode="json") if hasattr(event, "model_dump") else None
    text_content = event.get_plaintext()
    mentions_bot = bool(hasattr(event, "is_tome") and event.is_tome())
    author_id = str(event.get_user_id())
    author_name = extract_author_name(raw_data) or author_id
    platform_message_id = extract_platform_message_id(event, raw_data)
    platform_reply_id = extract_platform_reply_id(raw_data)
    has_media = detect_has_media(raw_data)
    content = build_normalized_content(
        raw_data=raw_data,
        text_content=text_content,
        adapter=str(getattr(bot, "type", "")) or None,
    )
    message_kind = resolve_message_kind(
        text_content=text_content,
        has_media=has_media,
    )

    return IngestedChatEvent(
        identity=identity,
        author_id=author_id,
        author_name=author_name,
        text_content=text_content,
        message_kind=message_kind,
        directed_to_bot=(identity.scene_type == "private" or mentions_bot),
        mentions_bot=mentions_bot,
        has_media=has_media,
        platform_message_id=platform_message_id,
        platform_reply_id=platform_reply_id,
        content=content,
        raw_data=build_debug_raw_payload(raw_data) if persist_raw_data else None,
    )


__all__ = [
    "IngestedChatEvent",
    "build_ingested_chat_event",
]
