"""Signal extraction helpers for the decision boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import AIDecisionContext

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


def extract_plaintext(event: "Event") -> str:
    """Extract normalized plaintext from one NoneBot event."""

    try:
        return event.get_plaintext().strip()
    except Exception:  # noqa: BLE001
        return ""


def is_private_like_event(event: "Event", user_id: str) -> bool:
    """Treat direct-message session IDs as private-like engagement scope."""

    session_id = getattr(event, "get_session_id", lambda: "")()
    return session_id == user_id


def build_decision_context(bot: "Bot", event: "Event") -> AIDecisionContext | None:
    """Build one decision context from a generic NoneBot event."""

    try:
        user_id = str(event.get_user_id())
    except Exception:  # noqa: BLE001
        return None

    is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
    return AIDecisionContext(
        bot_self_id=str(bot.self_id),
        user_id=user_id,
        message_text=extract_plaintext(event),
        is_tome=is_tome,
        is_private=is_private_like_event(event, user_id),
    )
