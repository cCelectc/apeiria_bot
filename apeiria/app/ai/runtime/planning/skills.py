"""Skill-selection planning boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.skills.service import ai_skill_service

if TYPE_CHECKING:
    from apeiria.ai.skills.runtime import AISkillSelectionResult


async def select_runtime_skills(
    *,
    message_text: str,
    conversation_summary: str | None,
) -> "AISkillSelectionResult":
    """Select skills for a runtime turn."""

    return await ai_skill_service.select_skills(
        message_text=message_text,
        conversation_summary=conversation_summary,
    )


__all__ = ["select_runtime_skills"]
