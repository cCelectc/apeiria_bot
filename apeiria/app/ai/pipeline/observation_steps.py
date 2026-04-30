"""Live observation side effects for reply orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.pipeline.memory_steps import record_live_memory_recall
from apeiria.app.ai.pipeline.relationship_steps import (
    build_relationship_target,
    update_relationship_state,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest


async def apply_reply_observation_effects(
    *,
    request: "AIRuntimeReplyRequest",
    current_time: "datetime",
) -> None:
    """Apply live observation writes before read-oriented context assembly."""

    del current_time

    identity = request.identity
    if request.runtime_mode == "message" and request.sentiment is not None:
        await update_relationship_state(
            target=build_relationship_target(identity, request.user_id),
            sentiment=request.sentiment,
            is_tome=request.is_tome,
        )

    await record_live_memory_recall(
        identity=identity,
        user_id=request.user_id,
        query_text=request.message_text,
    )


__all__ = ["apply_reply_observation_effects"]
