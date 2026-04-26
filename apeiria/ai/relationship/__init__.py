"""Relationship and emotion domain exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIRelationshipDelta,
    AIRelationshipEvent,
    AIRelationshipEventType,
    AIRelationshipState,
    EmotionProjection,
)
from .scope import build_affinity_scope_key
from .signals import derive_relationship_delta

if TYPE_CHECKING:
    from .scoring import (
        TONE_LABEL,
        apply_inactivity_decay,
        apply_relationship_delta,
        project_emotion,
    )
    from .service import AIRelationshipService, ai_relationship_service

__all__ = [
    "TONE_LABEL",
    "AIRelationshipDelta",
    "AIRelationshipEvent",
    "AIRelationshipEventType",
    "AIRelationshipService",
    "AIRelationshipState",
    "EmotionProjection",
    "ai_relationship_service",
    "apply_inactivity_decay",
    "apply_relationship_delta",
    "build_affinity_scope_key",
    "derive_relationship_delta",
    "project_emotion",
]

_LAZY_EXPORTS = {
    "AIRelationshipService": ".service",
    "TONE_LABEL": ".scoring",
    "ai_relationship_service": ".service",
    "apply_inactivity_decay": ".scoring",
    "apply_relationship_delta": ".scoring",
    "project_emotion": ".scoring",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
