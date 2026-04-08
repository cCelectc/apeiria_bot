"""Relationship and emotion domain for the Apeiria AI plugin rewrite."""

from .models import AIRelationshipDelta, AIRelationshipState, EmotionProjection
from .scope import build_affinity_scope_key
from .scoring import apply_relationship_delta, project_emotion
from .signals import derive_relationship_delta

__all__ = [
    "AIRelationshipDelta",
    "AIRelationshipState",
    "EmotionProjection",
    "apply_relationship_delta",
    "build_affinity_scope_key",
    "derive_relationship_delta",
    "project_emotion",
]
