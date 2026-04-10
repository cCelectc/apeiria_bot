"""Pure helpers for AI workbench preview assembly."""

from __future__ import annotations

from apeiria.app.ai.conversation.models import (
    AIContextTurnView,
    AIConversationTurnDetailView,
)


def select_latest_user_message(
    turns: list[AIConversationTurnDetailView],
) -> str | None:
    """Return the latest non-empty user message in the conversation."""

    for turn in reversed(turns):
        if turn.sender_type == "user" and turn.content_text.strip():
            return turn.content_text.strip()
    return None


def extract_tool_result_lines(
    turns: list[AIConversationTurnDetailView],
) -> tuple[str, ...]:
    """Return recent tool-result lines from conversation turns."""

    lines = [
        turn.content_text
        for turn in turns
        if turn.sender_type == "tool" and turn.content_text.strip()
    ]
    return tuple(lines[-4:])


def to_context_turns(
    turns: list[AIConversationTurnDetailView],
) -> list[AIContextTurnView]:
    """Drop workbench-only metadata and return prompt-ready turns."""

    return [
        AIContextTurnView(
            turn_id=turn.turn_id,
            sender_type=turn.sender_type,
            sender_id=turn.sender_id,
            content_text=turn.content_text,
            created_at=turn.created_at,
        )
        for turn in turns
    ]
