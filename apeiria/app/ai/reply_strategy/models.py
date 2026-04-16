"""Data models for the unified reply strategy pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

# ---------------------------------------------------------------------------
# Layer 1: Wake Gate
# ---------------------------------------------------------------------------

WakeEngagement = Literal["direct", "candidate", "drop"]


@dataclass(frozen=True)
class WakeContext:
    """Minimal signals for the wake-gate layer."""

    bot_self_id: str
    user_id: str
    message_text: str
    is_tome: bool
    is_private: bool
    is_future_task: bool


@dataclass(frozen=True)
class WakeSignal:
    """Result of the wake-gate evaluation."""

    should_process: bool
    engagement: WakeEngagement
    reason: str


# ---------------------------------------------------------------------------
# Layer 2: Initiative Budget
# ---------------------------------------------------------------------------


@dataclass
class InitiativeState:
    """Per-session in-memory state for initiative budgeting.

    Not persisted — resets when the process restarts.
    """

    session_id: str
    consecutive_silence: int = 0
    recent_reply_times: list[float] = field(default_factory=list)
    last_reply_at: float | None = None
    total_messages_seen: int = 0
    last_active_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class InitiativeBudgetResult:
    """Output of the initiative budget check."""

    should_evaluate: bool
    budget_score: float
    reason: str


# ---------------------------------------------------------------------------
# Layer 3: Social Judgment
# ---------------------------------------------------------------------------

SocialJudgmentAction = Literal["reply", "interject", "wait", "suppress"]
SocialJudgmentToolMode = Literal["allow", "avoid"]


@dataclass(frozen=True)
class SocialJudgmentInput:
    """Context provided to the LLM social judgment layer."""

    session_id: str
    scene_type: str
    message_text: str
    latest_user_turn_text: str | None
    conversation_summary: str | None
    relationship_context: str | None
    persona_id: str | None
    available_tool_names: tuple[str, ...]
    recent_turn_count: int
    recent_bot_turn_count: int
    last_bot_turn_at: datetime | None
    current_time: datetime
    runtime_mode: str
    engagement_type: WakeEngagement
    initiative_budget_score: float | None
    consecutive_silence_count: int


@dataclass(frozen=True)
class SocialJudgmentResult:
    """Structured output from the LLM social judgment."""

    action: SocialJudgmentAction
    should_speak: bool
    should_interject: bool
    should_wait: bool
    tool_mode: SocialJudgmentToolMode
    reason_codes: tuple[str, ...]
    reason_text: str
    evidence: dict[str, object]


# ---------------------------------------------------------------------------
# Pipeline: unified output
# ---------------------------------------------------------------------------

ReplyStrategyAction = Literal["reply", "interject", "silent", "drop"]
ReplyStrategyDecisionSource = Literal["wake_gate", "initiative", "llm", "fallback"]


@dataclass(frozen=True)
class ReplyStrategyDecision:
    """Final decision produced by the three-layer pipeline."""

    action: ReplyStrategyAction
    should_speak: bool
    tool_mode: SocialJudgmentToolMode
    reason_codes: tuple[str, ...]
    reason_text: str
    evidence: dict[str, object]
    decision_source: ReplyStrategyDecisionSource


def judgment_to_decision(
    result: SocialJudgmentResult,
    *,
    decision_source: ReplyStrategyDecisionSource = "llm",
) -> ReplyStrategyDecision:
    """Map a ``SocialJudgmentResult`` to a ``ReplyStrategyDecision``."""

    action = result.action
    mapped: ReplyStrategyAction
    if action in {"wait", "suppress"}:
        mapped = "silent"
    elif action == "interject":
        mapped = "interject"
    else:
        mapped = "reply"
    return ReplyStrategyDecision(
        action=mapped,
        should_speak=result.should_speak,
        tool_mode=result.tool_mode,
        reason_codes=result.reason_codes,
        reason_text=result.reason_text,
        evidence=result.evidence,
        decision_source=decision_source,
    )
