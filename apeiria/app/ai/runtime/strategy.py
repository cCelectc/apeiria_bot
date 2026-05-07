"""Runtime-facing hard-rule reply strategy contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MAX_HARD_RULE_EVIDENCE_ITEMS = 8

RuntimeHardRuleAction = Literal[
    "drop",
    "observe",
    "merge",
    "wait",
    "defer",
    "continue",
]

RuntimeHardRuleReasonCode = Literal[
    "duplicate_event",
    "bot_self_message",
    "empty_input",
    "initiative_disabled",
    "direct_signal",
    "private_message",
    "future_task",
    "ambient_candidate",
    "ambient_merge_window",
    "session_busy",
    "ambient_cooldown",
    "ambient_weak_relevance",
    "policy_denied",
]


@dataclass(frozen=True, slots=True)
class RuntimeHardRuleDecision:
    """Deterministic runtime decision before social judgment or generation."""

    action: RuntimeHardRuleAction
    reason_codes: tuple[RuntimeHardRuleReasonCode, ...]
    reason_text: str
    evidence: dict[str, Any]
    should_observe: bool
    should_reply: bool

    def __post_init__(self) -> None:
        if not self.reason_codes:
            msg = "Runtime hard-rule decisions require at least one reason code."
            raise ValueError(msg)

        if len(self.evidence) <= MAX_HARD_RULE_EVIDENCE_ITEMS:
            return

        bounded = dict(list(self.evidence.items())[:MAX_HARD_RULE_EVIDENCE_ITEMS])
        object.__setattr__(self, "evidence", bounded)
