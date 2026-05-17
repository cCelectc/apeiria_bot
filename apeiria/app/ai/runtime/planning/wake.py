"""Runtime reply strategy steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.relationship import ai_relationship_service
from apeiria.app.ai.reply_strategy.helpers import (
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
)
from apeiria.app.ai.reply_strategy.models import WakeContext
from apeiria.app.ai.reply_strategy.service import reply_strategy_service

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.session.context import RuntimeTurnInput
    from apeiria.conversation.models import ChatContextMessageView


async def resolve_initiative_bias(
    *,
    relationship_target: "AIRelationshipTarget",
) -> float:
    """Project the relationship state into an initiative bias."""

    projection = await ai_relationship_service.project_state(
        platform=relationship_target.platform,
        user_id=relationship_target.user_id,
    )
    return projection.initiative_bias


def build_fallback_wake_context(
    turn: "RuntimeTurnInput",
) -> WakeContext:
    """Synthesize a wake context for runtime paths that do not have one."""

    identity = turn.identity
    return WakeContext(
        bot_self_id=turn.sender_id,
        user_id=turn.user_id,
        message_text=turn.message_text,
        is_tome=turn.is_tome,
        is_private=identity.scene_type == "private",
        is_future_task=turn.runtime_mode == "future_task",
        has_media=bool(turn.source.media_parts or turn.source.media_diagnostics),
    )


async def decide_whether_to_speak(  # noqa: PLR0913
    *,
    turn: "RuntimeTurnInput",
    wake_context: WakeContext | None,
    turns: list["ChatContextMessageView"],
    conversation_summary: str | None,
    relationship_context: str | None,
    persona: "ReplyPersonaPromptBundleLike | None",
    allowed_tools: tuple["AIToolDefinition", ...],
    initiative_bias: float,
    model_target: "AIModelBindingTarget",
    current_time: "datetime",
    trace_id: str,
) -> "ReplyStrategyDecision":
    """Evaluate whether the bot should reply; log suppression when skipped."""

    identity = turn.identity
    if wake_context is None:
        wake_context = build_fallback_wake_context(turn)
    decision = await reply_strategy_service.evaluate(
        wake_context=wake_context,
        session_id=identity.session_id,
        scene_type=identity.scene_type,
        message_text=turn.message_text,
        latest_user_turn_text=latest_user_turn_text(turns),
        conversation_summary=conversation_summary,
        relationship_context=relationship_context,
        persona_id=persona.persona_id if persona is not None else None,
        available_tool_names=tuple(tool.name for tool in allowed_tools),
        recent_turn_count=len(turns),
        recent_bot_turn_count=count_recent_bot_turns(turns),
        last_bot_turn_at=latest_bot_turn_at(turns),
        current_time=current_time,
        runtime_mode=turn.runtime_mode,
        initiative_bias=initiative_bias,
        target=model_target,
    )
    if not decision.should_speak:
        logger.info(
            "AI trace {} suppressed {} reply for session {} action={} reasons={}",
            trace_id,
            turn.runtime_mode,
            identity.session_id,
            decision.action,
            ",".join(decision.reason_codes),
        )
    return decision
