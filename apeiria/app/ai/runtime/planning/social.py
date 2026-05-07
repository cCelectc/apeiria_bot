"""Social-decision handoff for runtime planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision

SocialSkipAction = Literal["drop", "observe", "wait", "defer"]
SocialSkipReasonCode = Literal[
    "policy_denied",
    "ambient_merge_window",
    "session_busy",
    "ambient_weak_relevance",
]


@dataclass(frozen=True, slots=True)
class SocialSkipProjection:
    """Runtime-facing terminal projection for a social no-reply decision."""

    action: SocialSkipAction
    reason_code: SocialSkipReasonCode
    reason_text: str
    evidence: dict[str, object]
    should_observe: bool


def summarize_social_decision(decision: "ReplyStrategyDecision") -> str:
    """Produce a prompt-facing summary of the social reply decision."""

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


def project_social_skip_decision(
    decision: "ReplyStrategyDecision",
) -> SocialSkipProjection:
    """Project a social no-reply decision into terminal runtime fields."""

    reason_text = decision.reason_text or ",".join(decision.reason_codes)
    reason_blob = " ".join((*decision.reason_codes, reason_text)).lower()
    if decision.action == "drop":
        action: SocialSkipAction = "drop"
        reason_code: SocialSkipReasonCode = "policy_denied"
        should_observe = False
    elif "wait" in reason_blob:
        action = "wait"
        reason_code = "ambient_merge_window"
        should_observe = True
    elif "busy" in reason_blob or "rate" in reason_blob:
        action = "defer"
        reason_code = "session_busy"
        should_observe = True
    else:
        action = "observe"
        reason_code = "ambient_weak_relevance"
        should_observe = True

    return SocialSkipProjection(
        action=action,
        reason_code=reason_code,
        reason_text=reason_text,
        evidence={
            "social_action": decision.action,
            "social_decision_source": decision.decision_source,
            "social_reason_codes": decision.reason_codes,
            "social_tool_mode": decision.tool_mode,
        },
        should_observe=should_observe,
    )


__all__ = [
    "SocialSkipProjection",
    "project_social_skip_decision",
    "summarize_social_decision",
]
