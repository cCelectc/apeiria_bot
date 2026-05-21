"""Pure helpers for access context extraction."""

from __future__ import annotations

from typing import Literal

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


def resolve_conversation_type(
    *,
    session_id: str,
    user_id: str,
    group_id: str | None,
    detail_type: str | None = None,
) -> ConversationType:
    """Normalize the conversation type used by access checks."""
    if group_id is not None:
        return "group"
    if is_private_session(
        session_id=session_id,
        user_id=user_id,
        detail_type=detail_type,
    ):
        return "private"
    return "other"


def is_private_session(
    *,
    session_id: str,
    user_id: str,
    detail_type: str | None = None,
) -> bool:
    """Return whether the primitive session data represents a private chat."""
    if detail_type == "private":
        return True
    return session_id == user_id
