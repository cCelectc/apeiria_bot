"""Reply strategy pipeline service — orchestrates the three layers."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.app.ai.reply_strategy.initiative import (
    check_initiative_budget,
    record_reply,
    record_silence,
)
from apeiria.app.ai.reply_strategy.models import (
    InitiativeState,
    ReplyStrategyDecision,
    ReplyStrategyDecisionSource,
    SocialJudgmentInput,
    WakeContext,
    judgment_to_decision,
)
from apeiria.app.ai.reply_strategy.social_judgment import (
    evaluate_social_judgment,
)
from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.model import AIModelBindingTarget

_MAX_TRACKED_SESSIONS = 500
_STATE_TTL_SECONDS = 3600.0  # 1 hour


def _drop_decision(reason: str) -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="drop",
        should_speak=False,
        tool_mode="avoid",
        reason_codes=(reason,),
        reason_text=reason,
        evidence={},
        decision_source="wake_gate",
    )


def _silent_decision(
    reason: str,
    source: ReplyStrategyDecisionSource = "initiative",
    evidence: dict | None = None,
) -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="silent",
        should_speak=False,
        tool_mode="avoid",
        reason_codes=(reason,),
        reason_text=reason,
        evidence=evidence or {},
        decision_source=source,
    )


class ReplyStrategyService:
    """Three-layer reply strategy pipeline.

    Layer 1 — Wake Gate:       pure rules, zero cost
    Layer 2 — Initiative:      per-session budget, no LLM
    Layer 3 — Social Judgment: LLM decides action + tool_mode
    """

    def __init__(self) -> None:
        self._states: dict[str, InitiativeState] = {}

    def get_initiative_state(self, session_id: str) -> InitiativeState:
        """Get or create per-session initiative state."""

        state = self._states.get(session_id)
        if state is None:
            self._maybe_evict()
            state = InitiativeState(session_id=session_id)
            self._states[session_id] = state
        state.last_active_at = time.time()
        return state

    async def evaluate(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        wake_context: WakeContext,
        session_id: str,
        scene_type: str,
        message_text: str,
        latest_user_turn_text: str | None,
        conversation_summary: str | None,
        relationship_context: str | None,
        persona_id: str | None,
        available_tool_names: tuple[str, ...],
        recent_turn_count: int,
        recent_bot_turn_count: int,
        last_bot_turn_at: "datetime | None",
        current_time: "datetime",
        runtime_mode: str,
        initiative_bias: float,
        target: "AIModelBindingTarget | None" = None,
    ) -> ReplyStrategyDecision:
        """Run the full three-layer pipeline."""

        # -- Layer 1: Wake Gate --
        wake = evaluate_wake(wake_context)
        if wake.engagement == "drop":
            return _drop_decision(wake.reason)

        state = self.get_initiative_state(session_id)
        now = time.time()

        # -- Layer 2: Initiative Budget (candidate only) --
        budget_score: float | None = None
        if wake.engagement == "candidate":
            record_silence(state)
            budget = check_initiative_budget(
                state,
                initiative_bias=initiative_bias,
                current_time=now,
            )
            budget_score = budget.budget_score
            if not budget.should_evaluate:
                logger.debug(
                    "reply_strategy: silent for session {} — {}",
                    session_id,
                    budget.reason,
                )
                return _silent_decision(
                    budget.reason,
                    source="initiative",
                    evidence={
                        "budget_score": budget.budget_score,
                        "consecutive_silence": state.consecutive_silence,
                    },
                )

        # -- Layer 3: Social Judgment (LLM) --
        judgment_input = SocialJudgmentInput(
            session_id=session_id,
            scene_type=scene_type,
            message_text=message_text,
            latest_user_turn_text=latest_user_turn_text,
            conversation_summary=conversation_summary,
            relationship_context=relationship_context,
            persona_id=persona_id,
            available_tool_names=available_tool_names,
            recent_turn_count=recent_turn_count,
            recent_bot_turn_count=recent_bot_turn_count,
            last_bot_turn_at=last_bot_turn_at,
            current_time=current_time,
            runtime_mode=runtime_mode,
            engagement_type=wake.engagement,
            initiative_budget_score=budget_score,
            consecutive_silence_count=state.consecutive_silence,
        )
        judgment = await evaluate_social_judgment(
            session,
            judgment_input=judgment_input,
            target=target,
        )
        decision = judgment_to_decision(judgment)

        logger.debug(
            "reply_strategy: session={} engagement={} → action={} source={} reason={}",
            session_id,
            wake.engagement,
            decision.action,
            decision.decision_source,
            decision.reason_text,
        )
        return decision

    def notify_replied(self, session_id: str) -> None:
        """Notify the initiative tracker that the bot replied."""

        state = self.get_initiative_state(session_id)
        record_reply(state)

    def _maybe_evict(self) -> None:
        """Evict stale sessions when the cache exceeds its cap."""

        if len(self._states) < _MAX_TRACKED_SESSIONS:
            return
        now = time.time()
        stale = [
            sid
            for sid, st in self._states.items()
            if now - st.last_active_at > _STATE_TTL_SECONDS
        ]
        for sid in stale:
            del self._states[sid]
        if len(self._states) >= _MAX_TRACKED_SESSIONS:
            oldest = sorted(self._states, key=lambda s: self._states[s].last_active_at)
            for sid in oldest[: len(oldest) // 4]:
                del self._states[sid]


def summarize_reply_strategy_decision(
    decision: ReplyStrategyDecision,
) -> str:
    """Produce a prompt-facing summary of the reply strategy decision."""

    codes = ", ".join(decision.reason_codes)
    policy_source = str(
        decision.evidence.get("policy_source") or decision.decision_source
    )
    return "\n".join(
        (
            f"Action: {decision.action}",
            f"Tool mode: {decision.tool_mode}",
            f"Reason codes: {codes or 'none'}",
            f"Reason: {decision.reason_text}",
            f"Policy source: {policy_source}",
        )
    )


reply_strategy_service = ReplyStrategyService()
