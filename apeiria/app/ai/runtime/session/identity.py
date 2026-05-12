"""Helpers for deriving managed AI session identity from runtime inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.sessions.models import (
    AISessionMessageType,
    AISessionSourceIdentity,
    NormalizedAISessionIdentity,
)

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatSessionIdentity


def derive_ai_session_source_identity(
    identity: "ChatSessionIdentity",
    *,
    platform_type: str | None = None,
    source_labels: dict[str, str] | None = None,
    diagnostic_raw_ids: dict[str, str] | None = None,
) -> AISessionSourceIdentity:
    """Derive the v1 managed AI session source from chat identity facts."""

    resolved_platform_type = platform_type or identity.platform
    message_type = _message_type(identity, platform_type=resolved_platform_type)
    subject_id = _subject_id(identity, message_type=message_type)
    return AISessionSourceIdentity(
        identity=NormalizedAISessionIdentity(
            session_id=identity.session_id,
            platform_id=identity.platform,
            platform_type=resolved_platform_type,
            message_type=message_type,
            subject_id=subject_id,
        ),
        source_labels=source_labels or _default_source_labels(identity, subject_id),
        diagnostic_raw_ids={
            **({"bot_id": identity.bot_id} if identity.bot_id else {}),
            **(diagnostic_raw_ids or {}),
        },
    )


def _message_type(
    identity: "ChatSessionIdentity",
    *,
    platform_type: str,
) -> AISessionMessageType:
    if platform_type == "web_chat" or identity.platform in {"webchat", "web_chat"}:
        return "web_chat"
    if identity.scene_type == "group":
        return "group"
    return "private"


def _subject_id(
    identity: "ChatSessionIdentity",
    *,
    message_type: AISessionMessageType,
) -> str:
    if message_type == "group":
        return identity.scene_id
    return identity.subject_id or identity.scene_id


def _default_source_labels(
    identity: "ChatSessionIdentity",
    subject_id: str,
) -> dict[str, str]:
    labels = {
        "platform": identity.platform,
        "scene_type": identity.scene_type,
        "subject": subject_id,
    }
    if identity.subject_id:
        labels["user_id"] = identity.subject_id
    return labels


__all__ = ["derive_ai_session_source_identity"]
