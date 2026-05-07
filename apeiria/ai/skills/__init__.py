"""Product-facing skill layer with lazy runtime/service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .catalog import AISkillMetadata
from .parser import AISkillFileDefinition

if TYPE_CHECKING:
    from .runtime import (
        AISkillActivation,
        AISkillCatalogEntry,
        AISkillRuntime,
        AISkillSelectionResult,
        ai_skill_runtime,
    )
    from .service import AISkillService, ai_skill_service

__all__ = [
    "AISkillActivation",
    "AISkillCatalogEntry",
    "AISkillFileDefinition",
    "AISkillMetadata",
    "AISkillRuntime",
    "AISkillSelectionResult",
    "AISkillService",
    "ai_skill_runtime",
    "ai_skill_service",
]

_LAZY_EXPORTS = {
    "AISkillActivation": ".runtime",
    "AISkillCatalogEntry": ".runtime",
    "AISkillRuntime": ".runtime",
    "AISkillSelectionResult": ".runtime",
    "AISkillService": ".service",
    "ai_skill_runtime": ".runtime",
    "ai_skill_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
