"""Pure heuristics for converting user messages into relationship deltas."""

from __future__ import annotations

from apeiria.app.ai.relationship.models import AIRelationshipDelta

_POSITIVE_TOKENS = (
    "谢谢",
    "感谢",
    "辛苦",
    "喜欢",
    "爱你",
    "抱抱",
    "厉害",
    "可爱",
)
_NEGATIVE_TOKENS = (
    "讨厌",
    "烦",
    "闭嘴",
    "滚",
    "笨",
    "傻",
    "气死",
)
_DIRECT_ENGAGEMENT_BONUS = 0.02
_POSITIVE_SIGNAL = 0.08
_NEGATIVE_SIGNAL = -0.12


def derive_relationship_delta(
    *,
    text: str,
    is_private: bool,
    is_tome: bool,
) -> AIRelationshipDelta | None:
    """Build a small deterministic relationship delta from one message."""

    normalized = text.strip().lower()
    if not normalized:
        return None

    score_delta = 0.0
    mood_tag: str | None = None
    reason_parts: list[str] = []

    if any(token in normalized for token in _POSITIVE_TOKENS):
        score_delta += _POSITIVE_SIGNAL
        mood_tag = "positive_contact"
        reason_parts.append("positive wording")
    if any(token in normalized for token in _NEGATIVE_TOKENS):
        score_delta += _NEGATIVE_SIGNAL
        mood_tag = "negative_contact"
        reason_parts.append("negative wording")
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
