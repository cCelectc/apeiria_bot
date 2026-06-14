"""Relationship and emotion domain exports."""

from __future__ import annotations

from .models import (
    AIRelationshipDelta,
    AIRelationshipEvent,
    AIRelationshipEventType,
    AIRelationshipState,
    EmotionProjection,
)
from .scoring import (
    apply_inactivity_decay,
    apply_relationship_delta,
    clamp_relationship_score,
    project_emotion,
    relationship_tier,
)
from .service import AIRelationshipService
from .signals import derive_relationship_delta

__all__ = [
    "AIRelationshipDelta",
    "AIRelationshipEvent",
    "AIRelationshipEventType",
    "AIRelationshipService",
    "AIRelationshipState",
    "EmotionProjection",
    "apply_inactivity_decay",
    "apply_relationship_delta",
    "clamp_relationship_score",
    "derive_relationship_delta",
    "project_emotion",
    "relationship_tier",
]
