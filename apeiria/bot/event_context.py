"""NoneBot-facing event normalization helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import get_driver

from apeiria.access.level import extract_group_id, resolve_conversation_type
from apeiria.access.models import AccessContext
from apeiria.conversation.identity import build_chat_session_identity

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.conversation.models import ChatSessionIdentity


def group_id_from_event(event: "Event") -> str | None:
    """Resolve a group id from common NoneBot event shapes."""

    group_id = getattr(event, "group_id", None)
    if group_id is not None:
        return str(group_id)

    try:
        user_id = event.get_user_id()
        return extract_group_id(event.get_session_id(), user_id)
    except Exception:  # noqa: BLE001
        return None


def build_access_context_from_event(
    _bot: "Bot",
    event: "Event",
) -> AccessContext | None:
    """Build one normalized access context from a NoneBot event."""

    try:
        user_id = event.get_user_id()
        session_id = event.get_session_id()
    except Exception:  # noqa: BLE001
        return None

    group_id = group_id_from_event(event)
    conversation_type = resolve_conversation_type(
        session_id=session_id,
        user_id=user_id,
        group_id=group_id,
        detail_type=getattr(event, "detail_type", None),
    )
    superusers = {
        str(item) for item in getattr(get_driver().config, "superusers", set())
    }
    return AccessContext(
        user_id=user_id,
        group_id=group_id,
        conversation_type=conversation_type,
        is_superuser=str(user_id) in superusers,
    )


def build_chat_session_identity_from_event(
    bot: "Bot",
    event: "Event",
) -> "ChatSessionIdentity | None":
    """Build a chat session identity from a NoneBot bot/event pair."""

    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        return None

    group_id = group_id_from_event(event)
    return build_chat_session_identity(
        platform=bot.type,
        bot_id=str(bot.self_id),
        user_id=str(user_id),
        group_id=group_id,
    )


__all__ = [
    "build_access_context_from_event",
    "build_chat_session_identity_from_event",
    "group_id_from_event",
]
