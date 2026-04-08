"""Pure helpers for relationship scoring and emotion projection."""

from __future__ import annotations

from apeiria.app.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipState,
    EmotionProjection,
)

_MIN_SCORE = -1.0
_MAX_SCORE = 1.0
_WARM_THRESHOLD = 0.6
_GUARDED_THRESHOLD = -0.4


def _clamp_score(value: float) -> float:
    return max(_MIN_SCORE, min(_MAX_SCORE, value))


def apply_relationship_delta(
    state: AIRelationshipState,
    delta: AIRelationshipDelta,
) -> AIRelationshipState:
    """Apply one deterministic delta to relationship state."""

    tags = list(state.mood_tags)
    if delta.mood_tag and delta.mood_tag not in tags:
        tags.append(delta.mood_tag)
    return AIRelationshipState(
        affinity_id=state.affinity_id,
        platform=state.platform,
        group_id=state.group_id,
        user_id=state.user_id,
        score=_clamp_score(state.score + delta.score_delta),
        mood_tags=tuple(tags[-3:]),
        last_event_at=state.last_event_at,
    )


def project_emotion(state: AIRelationshipState) -> EmotionProjection:
    """Project relationship state into lightweight response parameters."""

    score = state.score
    if score >= _WARM_THRESHOLD:
        return EmotionProjection(
            tone="warm",
            initiative_bias=0.35,
            warmth_bias=0.8,
        )
    if score <= _GUARDED_THRESHOLD:
        return EmotionProjection(
            tone="guarded",
            initiative_bias=-0.2,
            warmth_bias=-0.4,
        )
    return EmotionProjection(
        tone="neutral",
        initiative_bias=0.0,
        warmth_bias=0.1,
    )
