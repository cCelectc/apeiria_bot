"""Pure helpers for compact conversation summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import AIContextTurnView

_MAX_SUMMARY_TURNS = 4
_MAX_SUMMARY_LENGTH = 280


def build_short_conversation_summary(turns: list["AIContextTurnView"]) -> str | None:
    """Build a compact summary from the latest non-empty turns."""

    summary_lines = [
        _format_summary_turn(turn)
        for turn in turns[-_MAX_SUMMARY_TURNS:]
        if turn.content_text.strip()
    ]
    if not summary_lines:
        return None

    summary = " | ".join(summary_lines)
    if len(summary) <= _MAX_SUMMARY_LENGTH:
        return summary
    return f"{summary[: _MAX_SUMMARY_LENGTH - 1].rstrip()}…"


def _format_summary_turn(turn: "AIContextTurnView") -> str:
    speaker_map = {
        "user": "User",
        "bot": "Assistant",
        "system": "System",
        "tool": "Tool",
    }
    speaker = speaker_map.get(turn.sender_type, "Message")
    return f"{speaker}: {turn.content_text.strip()}"
