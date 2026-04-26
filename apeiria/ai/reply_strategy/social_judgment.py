"""Layer 3: LLM-backed social judgment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model import AIModelRouteQuery, model_gateway
from apeiria.ai.reply_strategy.models import (
    SocialJudgmentInput,
    SocialJudgmentResult,
)
from apeiria.ai.reply_strategy.prompt import (
    build_social_judgment_prompt,
    parse_social_judgment_response,
)

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
            prompt=build_social_judgment_prompt(judgment_input),
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
