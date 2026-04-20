"""Pure helpers for relationship scoring and emotion projection."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

from apeiria.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipState,
    EmotionProjection,
)

if TYPE_CHECKING:
    from datetime import datetime

_MIN_SCORE = -1.0
_MAX_SCORE = 1.0
_DECAY_START_AFTER_DAYS = 7
_DAILY_DECAY_RATE = 0.02
_NEUTRAL_EPSILON = 0.03
_MOOD_TAG_KEEP_SCORE = 0.1

# -- Emotion projection: 5-tier thresholds --
_CLOSE_THRESHOLD = 0.7
_WARM_THRESHOLD = 0.35
_GUARDED_THRESHOLD = -0.25
_COLD_THRESHOLD = -0.6

# -- Mood-tag bias adjustments --
_MOOD_TAG_INITIATIVE_ADJUST: dict[str, float] = {
    "playful_contact": 0.05,
    "negative_contact": -0.05,
    "direct_contact": 0.03,
}
_MOOD_TAG_WARMTH_ADJUST: dict[str, float] = {
    "positive_contact": 0.05,
    "playful_contact": 0.03,
    "negative_contact": -0.03,
}

# -- Per-tone base style modulation (Chinese, persona-safe) --
_TONE_BASE_MODULATION: dict[str, tuple[str, ...]] = {
    "close": (
        "保持人格核心设定不变。",
        "自然亲近，可以主动关心、开玩笑、使用亲昵称呼（如果人格允许）。",
        "语气可以更放松，像和老朋友聊天。",
    ),
    "warm": (
        "保持人格核心设定不变。",
        "友好热情，适度主动，保持自然的对话节奏。",
        "可以适当表达关心，但不过度亲昵。",
    ),
    "neutral": (
        "保持人格核心设定不变。",
        "使用人格基线的温度和主动性。",
    ),
    "guarded": (
        "保持人格核心设定不变。",
        "保持礼貌但拉开距离，减少主动发起话题。",
        "避免过于亲近的措辞。",
    ),
    "cold": (
        "保持人格核心设定不变。",
        "简短回应，不主动延伸话题，避免亲近表达。",
        "保持基本礼貌即可。",
    ),
}

# -- Mood-tag specific modulation overlays --
_MOOD_TAG_MODULATION: dict[str, str] = {
    "playful_contact": "对方最近在开玩笑 — 如果符合人格，可以用轻松的语气回应。",
    "positive_contact": "最近的互动比较愉快 — 可以自然地延续积极的氛围。",
    "negative_contact": "最近的互动有些紧张 — 措辞谨慎，避免激化。",
    "direct_contact": "对方在主动找你聊 — 认真回应，不敷衍。",
}

# -- Tone display labels (Chinese) --
TONE_LABEL: dict[str, str] = {
    "close": "亲近",
    "warm": "温暖",
    "neutral": "中性",
    "guarded": "疏远",
    "cold": "冷淡",
}


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
    """Project relationship state into lightweight response parameters.

    Uses a 5-tier score mapping (close/warm/neutral/guarded/cold) with
    mood-tag adjustments layered on top.  Style modulation strings are
    Chinese-language behavioral directives consumed by the prompt layer.
    """

    score = state.score
    tone, base_initiative, base_warmth = _score_to_base_tier(score)

    initiative_bias = base_initiative + _sum_mood_adjustments(
        state.mood_tags, _MOOD_TAG_INITIATIVE_ADJUST
    )
    warmth_bias = base_warmth + _sum_mood_adjustments(
        state.mood_tags, _MOOD_TAG_WARMTH_ADJUST
    )

    style_modulation = list(_TONE_BASE_MODULATION.get(tone, ()))
    for tag in state.mood_tags:
        overlay = _MOOD_TAG_MODULATION.get(tag)
        if overlay:
            style_modulation.append(overlay)

    return EmotionProjection(
        tone=tone,
        initiative_bias=round(initiative_bias, 3),
        warmth_bias=round(warmth_bias, 3),
        style_modulation=tuple(style_modulation),
    )


def _score_to_base_tier(score: float) -> tuple[str, float, float]:
    """Map a score to (tone, initiative_bias, warmth_bias)."""

    if score >= _CLOSE_THRESHOLD:
        return "close", 0.45, 0.9
    if score >= _WARM_THRESHOLD:
        return "warm", 0.25, 0.55
    if score > _GUARDED_THRESHOLD:
        return "neutral", 0.0, 0.1
    if score > _COLD_THRESHOLD:
        return "guarded", -0.15, -0.3
    return "cold", -0.3, -0.6


def _sum_mood_adjustments(
    mood_tags: tuple[str, ...],
    adjustment_map: dict[str, float],
) -> float:
    return sum(adjustment_map.get(tag, 0.0) for tag in mood_tags)
