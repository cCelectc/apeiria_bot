"""Pure helpers for relationship scoring and emotion projection."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

from apeiria.app.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipState,
    EmotionProjection,
)

if TYPE_CHECKING:
    from datetime import datetime

_MIN_SCORE = -1.0
_MAX_SCORE = 1.0
_WARM_THRESHOLD = 0.6
_GUARDED_THRESHOLD = -0.4
_DECAY_START_AFTER_DAYS = 7
_DAILY_DECAY_RATE = 0.02
_NEUTRAL_EPSILON = 0.03
_MOOD_TAG_KEEP_SCORE = 0.1


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


def apply_inactivity_decay(
    state: AIRelationshipState,
    *,
    current_time: datetime,
) -> AIRelationshipState:
    """Return a gently decayed state when the relationship has been inactive."""

    if state.last_event_at is None:
        return state

    decay_start_date = state.last_event_at.date() + timedelta(
        days=_DECAY_START_AFTER_DAYS
    )
    reference_date = decay_start_date
    if state.last_decay_at is not None and state.last_decay_at.date() > reference_date:
        reference_date = state.last_decay_at.date()
    decay_days = max((current_time.date() - reference_date).days, 0)
    if decay_days <= 0 or state.score == 0.0:
        return state

    decayed_score = state.score * ((1.0 - _DAILY_DECAY_RATE) ** decay_days)
    if abs(decayed_score) < _NEUTRAL_EPSILON:
        decayed_score = 0.0
    decayed_tags = state.mood_tags if abs(decayed_score) >= _MOOD_TAG_KEEP_SCORE else ()
    return replace(
        state,
        score=_clamp_score(decayed_score),
        mood_tags=decayed_tags,
        last_decay_at=current_time,
    )


def project_emotion(state: AIRelationshipState) -> EmotionProjection:
    """Project relationship state into lightweight response parameters."""

    score = state.score
    if score >= _WARM_THRESHOLD:
        return EmotionProjection(
            tone="warm",
            initiative_bias=0.35,
            warmth_bias=0.8,
            style_modulation=(
                "Keep the persona core unchanged.",
                "Use warmer wording and a slightly more proactive cadence.",
                (
                    "Light familiarity is acceptable only when it already fits "
                    "the persona."
                ),
            ),
        )
    if score <= _GUARDED_THRESHOLD:
        return EmotionProjection(
            tone="guarded",
            initiative_bias=-0.2,
            warmth_bias=-0.4,
            style_modulation=(
                "Keep the persona core unchanged.",
                "Stay polite but create a little more distance in tone.",
                "Reduce initiative and avoid over-familiar phrasing.",
            ),
        )
    return EmotionProjection(
        tone="neutral",
        initiative_bias=0.0,
        warmth_bias=0.1,
        style_modulation=(
            "Keep the persona core unchanged.",
            "Use the baseline persona warmth and initiative.",
        ),
    )
