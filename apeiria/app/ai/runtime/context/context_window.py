"""Runtime context window steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.conversation_context.context_window import (
    DEFAULT_CONTEXT_TOKEN_LIMIT,
    MAX_FETCH_MESSAGES,
    context_window_service,
)
from apeiria.app.ai.conversation_context.summary import (
    compress_conversation_history,
)
from apeiria.app.ai.sessions.repository import AISessionManagementRepository
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelGenerateResponse
    from apeiria.conversation.models import (
        ChatContextMessageView,
        ChatSessionContextSummary,
        ChatSessionIdentity,
    )


async def build_and_store_context_window(
    *,
    identity: "ChatSessionIdentity",
    model_context_window: int | None = None,
) -> tuple[list["ChatContextMessageView"], str | None]:
    """Fetch messages, split via dynamic window, compress overflow, store summary."""

    all_recent = await chat_session_service.list_recent_messages(
        identity,
        max_messages=MAX_FETCH_MESSAGES,
    )
    managed_session = await AISessionManagementRepository().get_session(
        identity.session_id,
    )
    reset_at = managed_session.context_reset_at if managed_session is not None else None
    if reset_at is not None:
        all_recent = [
            message for message in all_recent if message.created_at >= reset_at
        ]
    window = context_window_service.compute_window(
        all_recent,
        session_id=identity.session_id,
        context_token_limit=(
            model_context_window
            if model_context_window is not None and model_context_window > 0
            else DEFAULT_CONTEXT_TOKEN_LIMIT
        ),
    )
    turns = window.kept_messages

    conversation_summary = None
    if window.needs_compression and window.overflow_messages:
        existing_record = await chat_session_service.load_session_summary(identity)
        existing_summary = _valid_existing_summary_text(
            existing_record,
            reset_at=reset_at,
        )
        conversation_summary = await compress_conversation_history(
            list(window.overflow_messages),
            existing_summary=existing_summary,
            scene_type=identity.scene_type,
        )
        source_boundary = window.overflow_messages[-1]
        await chat_session_service.store_session_summary(
            identity,
            summary=conversation_summary,
            source_until_message_id=source_boundary.message_id,
            source_until_created_at=source_boundary.created_at,
        )
    else:
        existing_record = await chat_session_service.load_session_summary(identity)
        conversation_summary = project_conversation_summary(
            turns,
            existing_record,
            reset_at=reset_at,
        )
    return turns, conversation_summary


def _valid_existing_summary_text(
    summary_record: "ChatSessionContextSummary | None",
    *,
    reset_at: "datetime | None",
) -> str | None:
    if summary_record is None:
        return None
    if reset_at is not None and summary_record.source_until_created_at < reset_at:
        return None
    summary_text = summary_record.summary_text.strip()
    return summary_text or None


def project_conversation_summary(
    turns: list["ChatContextMessageView"],
    summary_record: "ChatSessionContextSummary | None",
    *,
    reset_at: "datetime | None",
) -> str | None:
    summary_text = _valid_existing_summary_text(summary_record, reset_at=reset_at)
    if summary_text is None or not turns or summary_record is None:
        return None
    oldest_turn = turns[0]
    if summary_record.source_until_created_at < oldest_turn.created_at:
        return summary_text
    return None


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
