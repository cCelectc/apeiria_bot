"""AI prompt-skill application entry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.skills import AISkillMetadata


class AISkillsEntry:
    """Application entry for prompt-skill management behavior."""

    def list_skills(self) -> list["AISkillMetadata"]:
        """List file-based prompt skills."""

        ensure_ai_runtime_support_initialized(source="admin_fallback")
        return ai_wiring.skill_service.list_skills()

    def reload_skills(self) -> tuple[str, ...]:
        ensure_ai_runtime_support_initialized(source="admin_fallback")
        return ai_wiring.skill_service.reload_skills()


ai_skills = AISkillsEntry()

__all__ = ["AISkillsEntry", "ai_skills"]
