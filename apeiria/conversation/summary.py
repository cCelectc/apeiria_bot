"""Pure helpers for compact conversation summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatContextMessageView

_MAX_SUMMARY_TURNS = 4
_MAX_SUMMARY_LENGTH = 280

_SPEAKER_MAP = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}


def build_short_conversation_summary(
    messages: list["ChatContextMessageView"],
) -> str | None:
    """Build a compact summary from the latest non-empty messages."""

    summary_lines = [
        _format_summary_message(msg)
        for msg in messages[-_MAX_SUMMARY_TURNS:]
        if msg.text_content.strip()
    ]
    if not summary_lines:
        return None

    summary = " | ".join(summary_lines)
    if len(summary) <= _MAX_SUMMARY_LENGTH:
        return summary
    return f"{summary[: _MAX_SUMMARY_LENGTH - 1].rstrip()}…"


def _format_summary_message(msg: "ChatContextMessageView") -> str:
    speaker = _SPEAKER_MAP.get(msg.author_role, "Message")
    if msg.author_name:
        speaker = msg.author_name
    return f"{speaker}: {msg.text_content.strip()}"
