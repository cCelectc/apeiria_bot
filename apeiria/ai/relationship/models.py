"""Relationship and emotion domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIRelationshipEventType = Literal["message", "manual", "decay"]


@dataclass(frozen=True)
class AIRelationshipState:
    """Structured relationship state for one user in the current database."""

    affinity_id: str
    platform: str
    user_id: str
    score: int
    mood_tags: tuple[str, ...]
    last_event_at: datetime | None
    last_decay_at: datetime | None = None


@dataclass(frozen=True)
class AIRelationshipDelta:
    """One deterministic score delta caused by an interaction."""

    score_delta: int
    mood_tag: str | None = None
    event_type: AIRelationshipEventType = "message"
    reason: str | None = None


@dataclass(frozen=True)
class AIRelationshipEvent:
    """One persisted relationship event for later inspection."""

    event_id: str
    affinity_id: str
    platform: str
    user_id: str
    scene_id: str | None
    event_type: AIRelationshipEventType
    score_delta: int
    score_after: int
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
