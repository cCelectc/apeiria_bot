"""Adapters for freezing pipeline state into runtime turn context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .context import RuntimeTurnSource, TurnContext

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelMessage
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision

    from .context import DeliveryTarget
    from .strategy import RuntimeHardRuleDecision
    from .tools import ToolExposurePlan


def build_turn_context(  # noqa: PLR0913
    *,
    trace_id: str,
    request: "AIRuntimeReplyRequest",
    inputs: "ReplyInputs",
    hard_decision: "RuntimeHardRuleDecision",
    social_decision: "ReplyStrategyDecision",
    delivery_target: "DeliveryTarget",
    prompt_messages: tuple["AIModelMessage", ...],
    tool_exposure_plan: "ToolExposurePlan",
    current_time: "datetime",
    prompt_diagnostics: dict[str, object] | None = None,
) -> TurnContext:
    """Freeze one behavior-preserving runtime turn context from pipeline state."""

    identity = request.identity
    return TurnContext(
        trace_id=trace_id,
        identity=identity,
        source=RuntimeTurnSource(
            runtime_mode=request.runtime_mode,
            message_text=request.message_text,
            source_message_id=request.source_message_id,
            user_id=request.user_id,
            direct_signal=request.is_tome,
            is_private=identity.scene_type == "private",
            event_dedupe_key=request.event_dedupe_key,
            event_dedupe_claimed=request.event_dedupe_claimed,
        ),
        delivery_target=delivery_target,
        current_time=current_time,
        model_target=inputs.model_target,
        tool_policy=inputs.tool_policy,
        tool_exposure_plan=tool_exposure_plan,
        prompt_messages=tuple(prompt_messages),
        prompt_diagnostics=prompt_diagnostics or {},
        hard_rule_decision=hard_decision,
        social_decision=social_decision,
    )
