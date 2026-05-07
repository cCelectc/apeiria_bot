"""Adapters for freezing pipeline state into runtime turn context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.session.context import TurnContext

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelMessage
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
    from apeiria.app.ai.runtime.session.context import (
        DeliveryTarget,
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision


def build_turn_context(  # noqa: PLR0913
    *,
    trace_id: str,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    hard_decision: "RuntimeHardRuleDecision",
    social_decision: "ReplyStrategyDecision",
    delivery_target: "DeliveryTarget",
    prompt_messages: tuple["AIModelMessage", ...],
    tool_exposure_plan: "ToolExposurePlan",
    current_time: "datetime",
    prompt_diagnostics: dict[str, object] | None = None,
) -> TurnContext:
    """Freeze one behavior-preserving runtime turn context."""

    return TurnContext(
        trace_id=trace_id,
        identity=turn.identity,
        source=turn.source,
        delivery_target=delivery_target,
        current_time=current_time,
        model_target=context.model_target,
        tool_policy=context.tool_policy,
        tool_exposure_plan=tool_exposure_plan,
        prompt_messages=tuple(prompt_messages),
        prompt_diagnostics=prompt_diagnostics or {},
        hard_rule_decision=hard_decision,
        social_decision=social_decision,
    )
