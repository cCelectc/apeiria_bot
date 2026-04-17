"""Layer 1: Pure-rule wake gate — zero cost, no state, no LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.reply_strategy.models import WakeContext, WakeEngagement, WakeSignal

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


def evaluate_wake(context: WakeContext) -> WakeSignal:
    """Evaluate whether a message should enter the AI pipeline at all.

    Returns a ``WakeSignal`` with one of three engagement levels:

    - ``drop``:      hard reject — message never enters the pipeline.
    - ``direct``:    skip initiative budget (Layer 2), proceed to LLM
                     judgment (Layer 3) directly.
    - ``candidate``: must pass initiative budget before reaching LLM.
    """

    if context.user_id == context.bot_self_id:
        should_process = False
        engagement: WakeEngagement = "drop"
        reason = "ignore_self_message"
    elif not context.message_text.strip():
        should_process = False
        engagement = "drop"
        reason = "empty_plaintext"
    elif context.is_future_task:
        should_process = True
        engagement = "direct"
        reason = "future_task"
    elif context.is_tome:
        should_process = True
        engagement = "direct"
        reason = "mentioned_bot"
    elif context.is_private:
        should_process = True
        engagement = "direct"
        reason = "private_message"
    elif not context.allow_group_initiative:
        should_process = False
        engagement = "drop"
        reason = "group_initiative_disabled"
    else:
        should_process = True
        engagement = "candidate"
        reason = "group_initiative_candidate"

    return WakeSignal(
        should_process=should_process,
        engagement=engagement,
        reason=reason,
    )


def extract_plaintext(event: "Event") -> str:
    """Extract normalized plaintext from one NoneBot event."""

    try:
        return event.get_plaintext().strip()
    except Exception:  # noqa: BLE001
        return ""


def is_private_like_event(event: "Event", user_id: str) -> bool:
    """Treat direct-message session IDs as private-like."""

    session_id = getattr(event, "get_session_id", lambda: "")()
    return session_id == user_id


def build_wake_context(
    bot: "Bot",
    event: "Event",
    *,
    allow_group_initiative: bool = True,
) -> WakeContext | None:
    """Build a wake context from a generic NoneBot event."""

    try:
        user_id = str(event.get_user_id())
    except Exception:  # noqa: BLE001
        return None

    is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
    return WakeContext(
        bot_self_id=str(bot.self_id),
        user_id=user_id,
        message_text=extract_plaintext(event),
        is_tome=is_tome,
        is_private=is_private_like_event(event, user_id),
        is_future_task=False,
        allow_group_initiative=allow_group_initiative,
    )
