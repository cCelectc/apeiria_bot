"""Pure helpers for access context extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from nonebot.adapters import Event


ConversationType = Literal["private", "group", "other"]


def extract_group_id(session_id: str, user_id: str) -> str | None:
    """Extract a group identifier from a session id when adapter data is absent."""
    if session_id == user_id:
        return None
    if "_" in session_id:
        parts = session_id.split("_")
        if len(parts) >= 2:  # noqa: PLR2004
            return parts[1] if parts[0] == "group" else parts[0]
    return None


def group_id_from_event(event: Event) -> str | None:
    """Resolve a group id from common event shapes."""
    group_id = getattr(event, "group_id", None)
    if group_id is not None:
        return str(group_id)

    try:
        user_id = event.get_user_id()
        return extract_group_id(event.get_session_id(), user_id)
    except Exception:  # noqa: BLE001
        return None


def resolve_conversation_type(
    event: Event,
    user_id: str,
    group_id: str | None,
) -> ConversationType:
    """Normalize the conversation type used by access checks."""
    if group_id is not None:
        return "group"
    if is_private_event(event, user_id):
        return "private"
    return "other"


def is_private_event(event: Event, user_id: str) -> bool:
    """Return whether the event is a private conversation."""
    detail_type = getattr(event, "detail_type", None)
    if detail_type == "private":
        return True
    try:
        return event.get_session_id() == user_id
    except Exception:  # noqa: BLE001
        return False
