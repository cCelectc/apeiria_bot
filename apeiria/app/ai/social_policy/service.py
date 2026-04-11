"""Explicit social-policy decision service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.app.ai.model import AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.social_policy.models import (
    AISocialPolicyDecision,
    AISocialPolicyInput,
    build_fallback_social_policy_decision,
    resolve_social_policy_task_class,
)
from apeiria.app.ai.social_policy.parsing import (
    build_social_policy_prompt,
    parse_social_policy_response,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.model import AIModelBindingTarget


class AISocialPolicyService:
    """LLM-backed runtime behavior policy."""

    async def decide(
        self,
        session: "AsyncSession",
        policy_input: AISocialPolicyInput,
        *,
        target: "AIModelBindingTarget | None" = None,
    ) -> AISocialPolicyDecision:
        fallback = build_fallback_social_policy_decision(policy_input)
        selected = await ai_model_facade.select_model(
            session,
            query=AIModelRouteQuery(
                task_class=resolve_social_policy_task_class(),
            ),
            target=target,
        )
        if selected is None:
            return fallback

        try:
            response = await ai_model_facade.generate_text(
                selected,
                prompt=build_social_policy_prompt(policy_input),
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning("AI social policy generation failed")
            return fallback

        if response is None:
            return fallback
        decision = parse_social_policy_response(response.content, fallback=fallback)
        evidence = dict(decision.evidence)
        evidence["policy_source"] = "llm" if decision is not fallback else "fallback"
        return AISocialPolicyDecision(
            action=decision.action,
            should_speak=decision.should_speak,
            should_interject=decision.should_interject,
            should_wait=decision.should_wait,
            tool_mode=decision.tool_mode,
            reason_codes=decision.reason_codes,
            reason_text=decision.reason_text,
            evidence=evidence,
        )


def summarize_social_policy_decision(decision: AISocialPolicyDecision) -> str:
    codes = ", ".join(decision.reason_codes)
    return (
        f"action={decision.action}; tool_mode={decision.tool_mode}; "
        f"reasons={codes or 'none'}; summary={decision.reason_text}"
    )


def count_recent_bot_turns(turns: "Iterable[object]") -> int:
    return sum(1 for turn in turns if getattr(turn, "sender_type", None) == "bot")


def latest_bot_turn_at(turns: "Iterable[object]") -> datetime | None:
    latest: datetime | None = None
    for turn in turns:
        if getattr(turn, "sender_type", None) != "bot":
            continue
        created_at = getattr(turn, "created_at", None)
        if isinstance(created_at, datetime):
            latest = created_at if latest is None or created_at > latest else latest
    return latest


def latest_user_turn_text(turns: "Iterable[object]") -> str | None:
    latest: str | None = None
    for turn in turns:
        if getattr(turn, "sender_type", None) != "user":
            continue
        content_text = getattr(turn, "content_text", None)
        if isinstance(content_text, str) and content_text.strip():
            latest = content_text
    return latest


ai_social_policy_service = AISocialPolicyService()
