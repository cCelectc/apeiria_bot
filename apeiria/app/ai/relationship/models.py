"""Relationship and emotion domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AIRelationshipState:
    """Structured relationship state for one user within one scene scope."""

    affinity_id: str
    platform: str
    group_id: str | None
    user_id: str
    score: float
    mood_tags: tuple[str, ...]
    last_event_at: datetime


@dataclass(frozen=True)
class AIRelationshipDelta:
    """One deterministic score delta caused by an interaction."""

    score_delta: float
    mood_tag: str | None = None


@dataclass(frozen=True)
class EmotionProjection:
    """Lightweight emotion projection for response configuration."""

    tone: str
    initiative_bias: float
    warmth_bias: float
