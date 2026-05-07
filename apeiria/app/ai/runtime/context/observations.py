"""Live observation side effects for reply orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.context.memories import record_live_memory_recall
from apeiria.app.ai.runtime.context.relationships import (
    build_relationship_target,
    update_relationship_state,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput


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


__all__ = ["apply_reply_observation_effects"]
