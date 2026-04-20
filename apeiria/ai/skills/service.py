"""Product-facing skill service with unified file + tool catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.skills.contracts import (
    build_file_skill_definition,
    build_skill_definition,
)
from apeiria.ai.skills.loader import (
    get_default_skills_directory,
    load_skills_from_directory,
)
from apeiria.ai.skills.runtime import ai_skill_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.ai.skills.catalog import AISkillDefinition
    from apeiria.ai.skills.parser import AISkillFileDefinition
    from apeiria.ai.skills.runtime import (
        AISkillActivation,
        AISkillCatalogEntry,
        AISkillSelectionResult,
    )
    from apeiria.ai.tools.models import AIToolPolicy
    from apeiria.ai.tools.service import AIToolService


def _get_ai_tool_service() -> "AIToolService":
    from apeiria.ai.tools.service import ai_tool_service

    return ai_tool_service


class AISkillService:
    """Unified skill service merging tool-based and file-based skills."""

    def __init__(self) -> None:
        self._initialized = False

    def ensure_initialized(
        self,
        *,
        skills_dir: "Path | None" = None,
    ) -> None:
        """Load file-based skills and sync tool-based skills.

        Safe to call multiple times; only the first call takes effect.
        """

        if self._initialized:
            return

        # Load file-based skills
        root = skills_dir or get_default_skills_directory()
        file_skills = load_skills_from_directory(root)
        ai_skill_runtime.register_file_skills(file_skills)

        tool_service = _get_ai_tool_service()
        tool_specs = tool_service.registry.list_tools()

        # Sync tool-based skills (file skills take priority on name
        # collision — register_tool_skill skips existing entries)
        for tool in tool_specs:
            ai_skill_runtime.register_tool_skill(
                skill_name=tool.name,
                description=tool.description,
                tags=tool.tags,
            )

        self._initialized = True
        logger.info(
            "Skill service initialized: {} file skills, {} tool skills",
            len(file_skills),
            len(tool_specs),
        )

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillDefinition"]:
        """Return all skills (tool + file) as product-facing definitions."""

        self.ensure_initialized()
        tool_service = _get_ai_tool_service()

        tool_skills = [
            build_skill_definition(tool)
            for tool in tool_service.list_tool_specs(policy)
        ]
        file_skills = [
            build_file_skill_definition(file_def)
            for file_def in ai_skill_runtime.list_file_skills()
        ]

        deduped_skills = {skill.skill_name: skill for skill in tool_skills}
        for skill in file_skills:
            deduped_skills[skill.skill_name] = skill
        return sorted(deduped_skills.values(), key=lambda s: s.skill_name)

    def list_catalog(self) -> list["AISkillCatalogEntry"]:
        """Return the unified runtime catalog."""

        self.ensure_initialized()
        return ai_skill_runtime.list_catalog()

    def list_file_skills(self) -> list["AISkillFileDefinition"]:
        """Return only file-based skills."""

        self.ensure_initialized()
        return ai_skill_runtime.list_file_skills()

    async def select_skills(
        self,
        session: "AsyncSession",
        *,
        message_text: str,
        conversation_summary: str | None,
    ) -> "AISkillSelectionResult":
        """LLM-based skill selection for a message."""

        self.ensure_initialized()
        return await ai_skill_runtime.select_skills_for_message(
            session,
            message_text=message_text,
            conversation_summary=conversation_summary,
        )

    def activate_skill_explicit(
        self,
        skill_name: str,
    ) -> "AISkillActivation | None":
        """Activate a skill by name (admin/test use)."""

        self.ensure_initialized()
        return ai_skill_runtime.activate_skill_explicit(skill_name)


ai_skill_service = AISkillService()

__all__ = ["AISkillService", "ai_skill_service"]
