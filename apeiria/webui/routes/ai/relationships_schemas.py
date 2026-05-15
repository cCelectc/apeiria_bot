"""Schema models for AI relationship routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from apeiria.ai.relationship import apply_inactivity_decay, project_emotion

if TYPE_CHECKING:
    from apeiria.ai.relationship import AIRelationshipEvent, AIRelationshipState


class AIRelationshipStateItem(BaseModel):
    affinity_id: str
    platform: str
    user_id: str
    score: int
    mood_tags: list[str] = []
    last_event_at: str | None = None
    last_decay_at: str | None = None
    projected_tone: str
    warmth_bias: float
    initiative_bias: float
    style_modulation: list[str] = []
    effective_score: int
    effective_mood_tags: list[str] = []
    effective_projected_tone: str
    effective_warmth_bias: float
    effective_initiative_bias: float
    effective_style_modulation: list[str] = []


class AIRelationshipEventItem(BaseModel):
    event_id: str
    affinity_id: str
    platform: str
    user_id: str
    scene_id: str | None = None
    event_type: str
    score_delta: int
    score_after: int
    mood_tag: str | None = None
    reason: str | None = None
    created_at: str


class AIRelationshipScoreUpdateRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=32)
    user_id: str = Field(min_length=1, max_length=64)
    scene_id: str | None = Field(default=None, max_length=128)
    score: int = Field(ge=-100, le=100)


def to_ai_relationship_state_item(
    item: "AIRelationshipState",
) -> AIRelationshipStateItem:
    projection = project_emotion(item)
    effective_state = apply_inactivity_decay(
        item,
        current_time=datetime.now(timezone.utc),
    )
    effective_projection = project_emotion(effective_state)
    return AIRelationshipStateItem(
        affinity_id=item.affinity_id,
        platform=item.platform,
        user_id=item.user_id,
        score=item.score,
        mood_tags=list(item.mood_tags),
        last_event_at=item.last_event_at.isoformat() if item.last_event_at else None,
        last_decay_at=item.last_decay_at.isoformat() if item.last_decay_at else None,
        projected_tone=projection.tone,
        warmth_bias=projection.warmth_bias,
        initiative_bias=projection.initiative_bias,
        style_modulation=list(projection.style_modulation),
        effective_score=effective_state.score,
        effective_mood_tags=list(effective_state.mood_tags),
        effective_projected_tone=effective_projection.tone,
        effective_warmth_bias=effective_projection.warmth_bias,
        effective_initiative_bias=effective_projection.initiative_bias,
        effective_style_modulation=list(effective_projection.style_modulation),
    )


def to_ai_relationship_event_item(
    item: "AIRelationshipEvent",
) -> AIRelationshipEventItem:
    return AIRelationshipEventItem(
        event_id=item.event_id,
        affinity_id=item.affinity_id,
        platform=item.platform,
        user_id=item.user_id,
        scene_id=item.scene_id,
        event_type=item.event_type,
        score_delta=item.score_delta,
        score_after=item.score_after,
        mood_tag=item.mood_tag,
        reason=item.reason,
        created_at=item.created_at.isoformat(),
    )
