"""Layer 3: LLM-backed social judgment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery, model_gateway
from apeiria.ai.prompting import (
    SocialJudgmentPromptInput,
    build_social_judgment_packet,
    render_messages,
)

from .models import (
    SocialJudgmentInput,
    SocialJudgmentResult,
)
from .prompt import parse_social_judgment_response

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelBindingTarget

_SOCIAL_JUDGMENT_TASK_CLASS = "planner_light"


def build_fallback_judgment(
    judgment_input: SocialJudgmentInput,
) -> SocialJudgmentResult:
    """Conservative fallback when the LLM is unavailable."""

    if (
        judgment_input.runtime_mode == "future_task"
        or judgment_input.scene_type == "private"
        or judgment_input.engagement_type == "direct"
    ):
        action = "reply"
    else:
        action = "suppress"

    should_speak = action in {"reply", "interject"}
    return SocialJudgmentResult(
        action=action,
        should_speak=should_speak,
        should_interject=False,
        should_wait=False,
        tool_mode="avoid",
        reason_codes=("fallback_social_judgment",),
        reason_text=(
            "Social judgment model was unavailable; used conservative fallback."
        ),
        evidence={
            "scene_type": judgment_input.scene_type,
            "runtime_mode": judgment_input.runtime_mode,
            "engagement_type": judgment_input.engagement_type,
            "policy_source": "fallback",
        },
    )


async def evaluate_social_judgment(
    *,
    judgment_input: SocialJudgmentInput,
    target: "AIModelBindingTarget | None" = None,
) -> SocialJudgmentResult:
    """Run the LLM social judgment and return a structured result."""

    fallback = build_fallback_judgment(judgment_input)

    selected = await model_gateway.select_model(
        query=AIModelRouteQuery(task_class=_SOCIAL_JUDGMENT_TASK_CLASS),
        target=target,
    )
    if selected is None:
        return fallback

    try:
        response = await model_gateway.generate_native(
            selected=selected,
            messages=render_messages(
                build_social_judgment_packet(
                    SocialJudgmentPromptInput(
                        scene_type=judgment_input.scene_type,
                        runtime_mode=judgment_input.runtime_mode,
                        engagement_type=judgment_input.engagement_type,
                        message_text=judgment_input.message_text,
                        latest_user_turn_text=judgment_input.latest_user_turn_text,
                        conversation_summary=judgment_input.conversation_summary,
                        relationship_context=judgment_input.relationship_context,
                        persona_id=judgment_input.persona_id,
                        available_tool_names=judgment_input.available_tool_names,
                        recent_turn_count=judgment_input.recent_turn_count,
                        recent_bot_turn_count=judgment_input.recent_bot_turn_count,
                        consecutive_silence_count=(
                            judgment_input.consecutive_silence_count
                        ),
                        current_time=judgment_input.current_time,
                        initiative_budget_score=(
                            judgment_input.initiative_budget_score
                        ),
                    )
                )
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning("AI social judgment generation failed")
        return fallback

    if response is None:
        return fallback

    decision = parse_social_judgment_response(
        response.content,
        fallback=fallback,
    )
    evidence = dict(decision.evidence)
    evidence["policy_source"] = "llm" if decision is not fallback else "fallback"
    return SocialJudgmentResult(
        action=decision.action,
        should_speak=decision.should_speak,
        should_interject=decision.should_interject,
        should_wait=decision.should_wait,
        tool_mode=decision.tool_mode,
        reason_codes=decision.reason_codes,
        reason_text=decision.reason_text,
        evidence=evidence,
    )
