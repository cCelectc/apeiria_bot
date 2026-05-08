"""Pure helpers for AI workbench preview assembly."""

from __future__ import annotations

from apeiria.conversation.models import (
    ChatContextMessageView,
    ChatMessageDetailView,
)


def select_latest_user_turn(
    turns: list[ChatMessageDetailView],
) -> ChatMessageDetailView | None:
    """Return the latest non-empty user turn in the conversation."""

    for turn in reversed(turns):
        if turn.turn_disposition == "observed":
            continue
        if turn.author_role == "user" and turn.text_content.strip():
            return turn
    return None


def select_latest_user_message(
    turns: list[ChatMessageDetailView],
) -> str | None:
    """Return the latest non-empty user message in the conversation."""

    latest_user_turn = select_latest_user_turn(turns)
    if latest_user_turn is None:
        return None
    return latest_user_turn.text_content.strip()


def extract_tool_result_lines(
    turns: list[ChatMessageDetailView],
) -> tuple[str, ...]:
    """Return recent tool-result lines from conversation turns."""

    lines = [
        turn.text_content
        for turn in turns
        if turn.author_role == "tool" and turn.text_content.strip()
    ]
    return tuple(lines[-4:])


def to_context_turns(
    turns: list[ChatMessageDetailView],
) -> list[ChatContextMessageView]:
    """Drop workbench-only metadata and return prompt-ready turns."""

    return [
        ChatContextMessageView(
            message_id=turn.message_id,
            author_role=turn.author_role,
            author_id=turn.author_id,
            author_name=turn.author_name,
            text_content=turn.text_content,
            content=turn.content,
            created_at=turn.created_at,
            reply_to_message_id=turn.reply_to_message_id,
            turn_disposition=turn.turn_disposition,
        )
        for turn in turns
    ]
