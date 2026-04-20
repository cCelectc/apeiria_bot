"""Runtime reply strategy steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.relationship.service import ai_relationship_service
from apeiria.ai.reply_strategy import (
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    reply_strategy_service,
)
from apeiria.ai.reply_strategy.models import WakeContext

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.ai.conversation.models import ChatContextMessageView
    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.pipeline.prompting import AIPersonaPromptBundleLike
    from apeiria.ai.pipeline.relationship_steps import AIRelationshipTarget
    from apeiria.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.ai.tools.models import AIToolSpec


async def resolve_initiative_bias(
    session: "AsyncSession",
    *,
    relationship_target: "AIRelationshipTarget",
) -> float:
    """Project the relationship state into an initiative bias."""

    projection = await ai_relationship_service.project_state(
        session,
        platform=relationship_target.platform,
        group_id=relationship_target.group_id,
        user_id=relationship_target.user_id,
    )
    return projection.initiative_bias


def build_fallback_wake_context(
    request: "AIRuntimeReplyRequest",
) -> WakeContext:
    """Synthesize a wake context for runtime paths that do not have one."""

    identity = request.identity
    return WakeContext(
        bot_self_id=request.sender_id,
        user_id=request.user_id,
        message_text=request.message_text,
        is_tome=request.is_tome,
        is_private=identity.scene_type == "private",
        is_future_task=request.runtime_mode == "future_task",
    )


async def decide_whether_to_speak(  # noqa: PLR0913
    session: "AsyncSession",
    *,
    request: "AIRuntimeReplyRequest",
    wake_context: WakeContext | None,
    turns: list["ChatContextMessageView"],
    conversation_summary: str | None,
    relationship_context: str | None,
    persona: "AIPersonaPromptBundleLike | None",
    allowed_tools: tuple["AIToolSpec", ...],
    initiative_bias: float,
    model_target: "AIModelBindingTarget",
    current_time: "datetime",
    trace_id: str,
) -> "ReplyStrategyDecision":
    """Evaluate whether the bot should reply; log suppression when skipped."""

    identity = request.identity
    if wake_context is None:
        wake_context = build_fallback_wake_context(request)
    decision = await reply_strategy_service.evaluate(
        session,
        wake_context=wake_context,
        session_id=identity.session_id,
        scene_type=identity.scene_type,
        message_text=request.message_text,
        latest_user_turn_text=latest_user_turn_text(turns),
        conversation_summary=conversation_summary,
        relationship_context=relationship_context,
        persona_id=persona.persona_id if persona is not None else None,
        available_tool_names=tuple(tool.name for tool in allowed_tools),
        recent_turn_count=len(turns),
        recent_bot_turn_count=count_recent_bot_turns(turns),
        last_bot_turn_at=latest_bot_turn_at(turns),
        current_time=current_time,
        runtime_mode=request.runtime_mode,
        initiative_bias=initiative_bias,
        target=model_target,
    )
    if not decision.should_speak:
        logger.info(
            "AI trace {} suppressed {} reply for session {} action={} reasons={}",
            trace_id,
            request.runtime_mode,
            identity.session_id,
            decision.action,
            ",".join(decision.reason_codes),
        )
    return decision
