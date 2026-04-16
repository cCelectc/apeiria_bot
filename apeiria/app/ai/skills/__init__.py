"""Product-facing skill layer."""

from .catalog import AISkillContract, AISkillDefinition
from .parser import AISkillFileDefinition
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
    "AISkillContract",
    "AISkillDefinition",
    "AISkillFileDefinition",
    "AISkillRuntime",
    "AISkillSelectionResult",
    "AISkillService",
    "ai_skill_runtime",
    "ai_skill_service",
]
