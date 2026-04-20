"""Pure helpers for canonical chat session identity."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from apeiria.ai.conversation.models import (
    ChatContextMessageView,
    ChatSessionIdentity,
    SceneType,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


def _normalize_scene(group_id: str | None) -> tuple[SceneType, str]:
    if group_id is not None:
        return "group", group_id
    return "private", ""


def _build_session_hash(
    platform: str,
    bot_id: str,
    scene_type: SceneType,
    scene_id: str,
) -> str:
    payload = json.dumps(
        {
            "platform": platform,
            "bot_id": bot_id,
            "scene_type": scene_type,
            "scene_id": scene_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"session_{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_participant_subject_id(
    *,
    scene_type: SceneType,
    scene_id: str,
    user_id: str,
) -> str:
    """Build a stable scene-local participant id for group-scoped state."""

    payload = json.dumps(
        {
            "scene_type": scene_type,
            "scene_id": scene_id,
            "user_id": user_id,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"participant_{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def build_chat_session_identity(
    *,
    platform: str,
    bot_id: str,
    user_id: str,
    group_id: str | None = None,
) -> ChatSessionIdentity:
    """Build the canonical chat session identity."""

    scene_type, scene_id = _normalize_scene(group_id or None)
    if scene_type == "private":
        scene_id = user_id

    return ChatSessionIdentity(
        session_id=_build_session_hash(
            platform,
            bot_id,
            scene_type,
            scene_id,
        ),
        platform=platform,
        bot_id=bot_id,
        scene_type=scene_type,
        scene_id=scene_id,
        subject_id=user_id if scene_type == "private" else None,
    )


def build_chat_session_identity_from_event(
    bot: Bot,
    event: Event,
) -> ChatSessionIdentity | None:
    """Build a chat session identity from a NoneBot bot/event pair."""

    from apeiria.access.level import group_id_from_event

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


def trim_message_window(
    messages: list[ChatContextMessageView],
    *,
    max_messages: int,
) -> list[ChatContextMessageView]:
    """Return the latest `max_messages` records for short-term context use."""

    if max_messages <= 0:
        return []
    return messages[-max_messages:]
