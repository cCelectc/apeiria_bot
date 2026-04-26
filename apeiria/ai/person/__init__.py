"""Person profile boundary exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIPersonMemoryPoint,
    AIPersonMemoryPointCategory,
    AIPersonProfileDefinition,
    AIPersonPromptProfile,
)

if TYPE_CHECKING:
    from .service import AIPersonProfileService, ai_person_profile_service

__all__ = [
    "AIPersonMemoryPoint",
    "AIPersonMemoryPointCategory",
    "AIPersonProfileDefinition",
    "AIPersonProfileService",
    "AIPersonPromptProfile",
    "ai_person_profile_service",
]

_LAZY_EXPORTS = {
    "AIPersonProfileService": ".service",
    "ai_person_profile_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
