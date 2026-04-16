"""Relationship and emotion domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIRelationshipEventType = Literal["message", "manual", "absence_decay"]


@dataclass(frozen=True)
class AIRelationshipState:
    """Structured relationship state for one user within one scene scope."""

    affinity_id: str
    platform: str
    group_id: str | None
    user_id: str
    score: float
    mood_tags: tuple[str, ...]
    last_event_at: datetime | None
    last_decay_at: datetime | None = None


@dataclass(frozen=True)
class AIRelationshipDelta:
    """One deterministic score delta caused by an interaction."""

    score_delta: float
    mood_tag: str | None = None
    event_type: AIRelationshipEventType = "message"
    reason: str | None = None


@dataclass(frozen=True)
class AIRelationshipEvent:
    """One persisted relationship event for later inspection."""

    event_id: str
    affinity_id: str
    platform: str
    group_id: str | None
    user_id: str
    event_type: AIRelationshipEventType
    score_delta: float
    score_after: float
    mood_tag: str | None
    reason: str | None
    created_at: datetime


@dataclass(frozen=True)
class EmotionProjection:
    """Lightweight emotion projection for response configuration.

    ``tone`` is one of: close, warm, neutral, guarded, cold.
    """

    tone: str
    initiative_bias: float
    warmth_bias: float
    style_modulation: tuple[str, ...] = ()
