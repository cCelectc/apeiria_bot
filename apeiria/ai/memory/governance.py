"""Deterministic governance for extracted memory candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.memory.models import AIMemoryGovernanceDecision

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryExtractionCandidate,
        AIMemoryTargetScope,
    )

_MIN_ACTIVE_CONFIDENCE = 0.55
_MIN_ACTIVE_SALIENCE = 0.35
_MIN_SUBJECTIVE_ACTIVE_CONFIDENCE = 0.8
_MIN_PREFERENCE_ACTIVE_CONFIDENCE = 0.75


def govern_extracted_memory(
    candidate: "AIMemoryExtractionCandidate",
    *,
    scene_type: str = "private",
) -> AIMemoryGovernanceDecision:
    """Apply conservative first-mechanism governance to one candidate."""

    target_scope = decide_candidate_scope(candidate, scene_type=scene_type)
    if candidate.action == "noop":
        return AIMemoryGovernanceDecision(
            action="reject",
            lifecycle_state=None,
            use_mode="ignore",
            target_scope=target_scope,
            reason="candidate requested noop",
        )
    if candidate.confidence < _MIN_ACTIVE_CONFIDENCE:
        return AIMemoryGovernanceDecision(
            action="reject",
            lifecycle_state=None,
            use_mode="ignore",
            target_scope=target_scope,
            reason="candidate confidence below activation threshold",
        )
    if candidate.memory_kind in {"impression", "relationship"}:
        return AIMemoryGovernanceDecision(
            action="accept",
            lifecycle_state=(
                "active"
                if candidate.confidence >= _MIN_SUBJECTIVE_ACTIVE_CONFIDENCE
                and candidate.salience >= _MIN_ACTIVE_SALIENCE
                else "candidate"
            ),
            use_mode="silent",
            target_scope=target_scope,
            reason="subjective memory defaults to silent use",
        )
    if (
        candidate.memory_kind == "preference"
        and candidate.confidence >= _MIN_PREFERENCE_ACTIVE_CONFIDENCE
    ):
        return AIMemoryGovernanceDecision(
            action="accept",
            lifecycle_state="active",
            use_mode="context",
            target_scope=target_scope,
            reason="explicit or high-confidence preference",
        )
    if candidate.salience < _MIN_ACTIVE_SALIENCE:
        return AIMemoryGovernanceDecision(
            action="accept",
            lifecycle_state="candidate",
            use_mode="ignore",
            target_scope=target_scope,
            reason="candidate salience below activation threshold",
        )
    return AIMemoryGovernanceDecision(
        action="accept",
        lifecycle_state="active",
        use_mode="context",
        target_scope=target_scope,
        reason="candidate passed deterministic governance",
    )


def decide_candidate_scope(
    candidate: "AIMemoryExtractionCandidate",
    *,
    scene_type: str,
) -> "AIMemoryTargetScope":
    """Choose a conservative first-mechanism scope for one candidate."""

    if candidate.scope_hint != "auto":
        return candidate.scope_hint
    if candidate.memory_kind in {"preference", "relationship", "impression"}:
        return "participant" if scene_type == "group" else "user"
    if candidate.memory_kind == "fact":
        return "participant" if scene_type == "group" else "user"
    return "scene"


def default_use_mode_for_manual_memory(memory_kind: str) -> str:
    """Return first-mechanism use mode for explicit operator/tool writes."""

    if memory_kind in {"relationship", "impression"}:
        return "silent"
    return "context"
