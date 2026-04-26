"""Runtime context window steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.conversation.context_window import (
    MAX_FETCH_MESSAGES,
    context_window_service,
)
from apeiria.ai.conversation.summary import (
    build_short_conversation_summary,
    compress_conversation_history,
)
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from apeiria.ai.model.adapter import AIModelGenerateResponse
    from apeiria.conversation.models import (
        ChatContextMessageView,
        ChatSessionIdentity,
    )


async def build_and_store_context_window(
    *,
    identity: "ChatSessionIdentity",
) -> tuple[list["ChatContextMessageView"], str | None]:
    """Fetch messages, split via dynamic window, compress overflow, store summary."""

    all_recent = await chat_session_service.list_recent_messages(
        identity,
        max_messages=MAX_FETCH_MESSAGES,
    )
    window = context_window_service.compute_window(
        all_recent,
        session_id=identity.session_id,
    )
    turns = window.kept_messages

    if window.needs_compression:
        existing_summary = await chat_session_service.load_session_summary(
            identity,
        )
        conversation_summary = await compress_conversation_history(
            window.overflow_messages,
            existing_summary=existing_summary,
            scene_type=identity.scene_type,
        )
    else:
        conversation_summary = build_short_conversation_summary(turns)

    await chat_session_service.store_summary_text(
        identity,
        summary=conversation_summary,
    )
    return turns, conversation_summary


def record_context_usage(
    session_id: str,
    *,
    response: "AIModelGenerateResponse",
    message_count: int,
) -> None:
    """Feed actual prompt token usage back to the context window calibrator."""

    raw = response.raw
    if not isinstance(raw, dict):
        return
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        return
    prompt_tokens = usage.get("prompt_tokens")
    if not isinstance(prompt_tokens, int) or prompt_tokens <= 0:
        return
    context_window_service.record_usage(
        session_id,
        prompt_tokens=prompt_tokens,
        message_count=message_count,
    )
