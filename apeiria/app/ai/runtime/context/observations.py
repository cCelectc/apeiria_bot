"""Live observation side effects for reply orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.context.memories import record_live_memory_recall
from apeiria.app.ai.runtime.context.relationships import (
    build_relationship_target,
    update_relationship_state,
)
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.conversation.models import ChatSessionIdentity


async def apply_reply_observation_effects(
    *,
    turn: "RuntimeTurnInput",
    current_time: "datetime",
) -> None:
    """Apply live observation writes before read-oriented context assembly."""

    del current_time

    identity = turn.identity
    if turn.runtime_mode == "message" and turn.sentiment is not None:
        await update_relationship_state(
            target=build_relationship_target(identity, turn.user_id),
            sentiment=turn.sentiment,
            is_tome=turn.is_tome,
        )

    await record_live_memory_recall(
        identity=identity,
        user_id=turn.user_id,
        query_text=turn.message_text,
    )


async def persist_observed_conversation_turn(
    *,
    identity: "ChatSessionIdentity",
    source_message_id: str | None,
    author_id: str,
    text_content: str,
) -> None:
    """Persist observed ambient input as thin conversation context."""

    if source_message_id is not None:
        existing = await chat_session_service.mark_message_observed(
            message_id=source_message_id,
        )
        if existing is not None:
            return
    await chat_session_service.append_observed_turn(
        identity,
        author_id=author_id,
        text_content=text_content,
        platform_message_id=source_message_id,
    )


__all__ = ["apply_reply_observation_effects", "persist_observed_conversation_turn"]
