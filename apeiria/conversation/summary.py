"""Pure helpers for compact conversation summaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatContextMessageView

_SPEAKER_MAP = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}


def build_short_conversation_summary(
    messages: list["ChatContextMessageView"],
) -> str | None:
    """Build a stable fallback excerpt from the selected overflow messages."""

    summary_lines = [
        _format_summary_message(msg) for msg in messages if msg.text_content.strip()
    ]
    if not summary_lines:
        return None
    return "\n".join(summary_lines)


def _format_summary_message(msg: "ChatContextMessageView") -> str:
    speaker = _SPEAKER_MAP.get(msg.author_role, "Message")
    if msg.author_name:
        speaker = msg.author_name
    normalized = " ".join(msg.text_content.strip().split())
    return f"{speaker}: {normalized}"
