"""Turn-level statistic helpers migrated from social_policy.service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def count_recent_bot_turns(turns: "Iterable[object]") -> int:
    """Count assistant turns in a recent turn list."""

    return sum(
        1
        for turn in turns
        if getattr(turn, "author_role", None) == "assistant"
        or getattr(turn, "sender_type", None) == "bot"
    )


def latest_bot_turn_at(turns: "Iterable[object]") -> datetime | None:
    """Return the creation time of the most recent assistant turn."""

    latest: datetime | None = None
    for turn in turns:
        if (
            getattr(turn, "author_role", None) != "assistant"
            and getattr(turn, "sender_type", None) != "bot"
        ):
            continue
        created_at = getattr(turn, "created_at", None)
        if isinstance(created_at, datetime):
            latest = created_at if latest is None or created_at > latest else latest
    return latest


def latest_user_turn_text(turns: "Iterable[object]") -> str | None:
    """Return the text of the most recent user turn."""

    latest: str | None = None
    for turn in turns:
        if getattr(turn, "turn_disposition", None) == "observed":
            continue
        if (
            getattr(turn, "author_role", None) != "user"
            and getattr(turn, "sender_type", None) != "user"
        ):
            continue
        content_text = getattr(turn, "text_content", None)
        if content_text is None:
            content_text = getattr(turn, "content_text", None)
        if isinstance(content_text, str) and content_text.strip():
            latest = content_text
    return latest
