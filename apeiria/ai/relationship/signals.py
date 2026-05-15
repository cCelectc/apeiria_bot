"""Semantic sentiment-driven relationship delta derivation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.relationship.models import AIRelationshipDelta

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMessageSentiment

_POLARITY_BASE_DELTA: dict[str, int] = {
    "positive": 1,
    "negative": -2,
    "playful": 1,
    "neutral": 0,
}

_POLARITY_MOOD_TAG: dict[str, str] = {
    "positive": "positive_contact",
    "negative": "negative_contact",
    "playful": "playful_contact",
}

_HIGH_INTENSITY_THRESHOLD = 0.85
_MEDIUM_INTENSITY_THRESHOLD = 0.45


def derive_relationship_delta(
    *,
    sentiment: "AIMessageSentiment",
    is_private: bool,
    is_tome: bool,
) -> AIRelationshipDelta | None:
    """Build a relationship delta from LLM-analyzed message sentiment."""

    if not is_private and not is_tome:
        return None

    base_delta = _POLARITY_BASE_DELTA.get(sentiment.polarity, 0)
    score_delta = _scale_delta(base_delta, sentiment.intensity)

    mood_tag = _POLARITY_MOOD_TAG.get(sentiment.polarity)
    reason_parts: list[str] = []

    if base_delta != 0:
        reason_parts.append(
            f"{sentiment.polarity} sentiment (intensity={sentiment.intensity:.2f})"
        )

    if mood_tag is None and sentiment.polarity == "neutral":
        mood_tag = "direct_contact"
    reason_parts.append("direct engagement")

    if score_delta == 0:
        return None

    return AIRelationshipDelta(
        score_delta=score_delta,
        mood_tag=mood_tag,
        event_type="message",
        reason=", ".join(reason_parts) or None,
    )


def _scale_delta(base_delta: int, intensity: float) -> int:
    if base_delta == 0:
        return 0
    bounded_intensity = max(0.0, min(1.0, intensity))
    if base_delta > 0:
        return 2 if bounded_intensity >= _HIGH_INTENSITY_THRESHOLD else 1
    if bounded_intensity >= _HIGH_INTENSITY_THRESHOLD:
        return -3
    return -2 if bounded_intensity >= _MEDIUM_INTENSITY_THRESHOLD else -1
