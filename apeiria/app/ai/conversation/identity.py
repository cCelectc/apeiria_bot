"""Pure helpers for canonical AI conversation identity."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from apeiria.app.ai.conversation.models import (
    AIContextTurnView,
    AIConversationIdentity,
    ScopeType,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


def _normalize_scope(group_id: str | None) -> tuple[ScopeType, str]:
    if group_id is not None:
        return "group", group_id
    return "private", ""


def _build_conversation_hash(
    platform: str,
    bot_id: str,
    scope_type: ScopeType,
    scope_id: str,
) -> str:
    payload = json.dumps(
        {
            "platform": platform,
            "bot_id": bot_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"conv_{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_participant_subject_id(
    *,
    scope_type: ScopeType,
    scope_id: str,
    user_id: str,
) -> str:
    """Build a stable scene-local participant id for group-scoped AI state."""

    payload = json.dumps(
        {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "user_id": user_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"participant_{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_conversation_identity(
    *,
    platform: str,
    bot_id: str,
    user_id: str,
    group_id: str | None = None,
) -> AIConversationIdentity:
    """Build the canonical AI conversation identity."""

    scope_type, scope_id = _normalize_scope(group_id or None)
    if scope_type == "private":
        scope_id = user_id

    return AIConversationIdentity(
        conversation_id=_build_conversation_hash(
            platform,
            bot_id,
            scope_type,
            scope_id,
        ),
        platform=platform,
        bot_id=bot_id,
        scope_type=scope_type,
        scope_id=scope_id,
        subject_user_id=user_id if scope_type == "private" else None,
    )


def build_conversation_identity_from_event(
    bot: Bot,
    event: Event,
) -> AIConversationIdentity | None:
    """Build a conversation identity from a NoneBot bot/event pair."""

    from apeiria.app.access import group_id_from_event

    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        return None

    group_id = group_id_from_event(event)
    return build_conversation_identity(
        platform=bot.type,
        bot_id=str(bot.self_id),
        user_id=str(user_id),
        group_id=group_id,
    )


def trim_turn_window(
    turns: list[AIContextTurnView],
    *,
    max_turns: int,
) -> list[AIContextTurnView]:
    """Return the latest `max_turns` turns for short-term context use."""

    if max_turns <= 0:
        return []
    return turns[-max_turns:]
