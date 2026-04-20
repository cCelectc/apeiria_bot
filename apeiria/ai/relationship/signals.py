"""Semantic sentiment-driven relationship delta derivation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.relationship.models import AIRelationshipDelta

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMessageSentiment

_DIRECT_ENGAGEMENT_BONUS = 0.02

_POLARITY_BASE_DELTA: dict[str, float] = {
    "positive": 0.08,
    "negative": -0.12,
    "playful": 0.05,
    "neutral": 0.0,
}

_POLARITY_MOOD_TAG: dict[str, str] = {
    "positive": "positive_contact",
    "negative": "negative_contact",
    "playful": "playful_contact",
}


def derive_relationship_delta(
    *,
    sentiment: "AIMessageSentiment",
    is_private: bool,
    is_tome: bool,
) -> AIRelationshipDelta | None:
    """Build a relationship delta from LLM-analyzed message sentiment."""

    base_delta = _POLARITY_BASE_DELTA.get(sentiment.polarity, 0.0)
    score_delta = base_delta * max(sentiment.intensity, 0.3)

    mood_tag = _POLARITY_MOOD_TAG.get(sentiment.polarity)
    reason_parts: list[str] = []

    if base_delta != 0.0:
        reason_parts.append(
            f"{sentiment.polarity} sentiment (intensity={sentiment.intensity:.2f})"
        )

    if is_private or is_tome:
        score_delta += _DIRECT_ENGAGEMENT_BONUS
        if mood_tag is None:
            mood_tag = "direct_contact"
        reason_parts.append("direct engagement")

    if score_delta == 0.0:
        return None

    return AIRelationshipDelta(
        score_delta=score_delta,
        mood_tag=mood_tag,
        event_type="message",
        reason=", ".join(reason_parts) or None,
    )
