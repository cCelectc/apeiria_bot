"""Product-facing skill service with unified file + tool catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.skills.contracts import (
    build_file_skill_metadata,
    build_tool_skill_metadata,
)
from apeiria.ai.skills.loader import (
    get_default_skills_directory,
    load_skills_from_sources,
)
from apeiria.ai.skills.runtime import ai_skill_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.ai.skills.catalog import AISkillMetadata
    from apeiria.ai.skills.parser import AISkillFileDefinition
    from apeiria.ai.skills.runtime import (
        AISkillActivation,
        AISkillCatalogEntry,
    )
    from apeiria.ai.tools.models import AIToolDefinition, AIToolPolicy
    from apeiria.ai.tools.service import AIToolService


def _get_ai_tool_service() -> "AIToolService":
    from apeiria.ai.tools.service import ai_tool_service

    return ai_tool_service


class AISkillService:
    """Unified skill service merging tool-based and file-based skills."""

    def __init__(self) -> None:
        self._initialized = False
        self._loaded_skill_sources: set[Path] = set()

    def ensure_initialized(
        self,
        *,
        skills_dir: "Path | None" = None,
        skill_sources: tuple["Path", ...] = (),
    ) -> None:
        """Load file-based skills and sync tool-based skills.

        Safe to call multiple times. New skill sources may be supplied by the
        plugin lifecycle coordinator and are scanned once.
        """

        was_initialized = self._initialized
        sources = _skill_sources(
            skills_dir=skills_dir,
            extra_sources=skill_sources,
        )
        new_sources = tuple(
            source for source in sources if source not in self._loaded_skill_sources
        )
        if new_sources:
            file_skills = load_skills_from_sources(new_sources)
            ai_skill_runtime.register_file_skills(file_skills)
            self._loaded_skill_sources.update(new_sources)
        elif was_initialized:
            file_skills = ai_skill_runtime.list_file_skills()
        else:
            file_skills = []

        self._initialized = True

        tool_skills = self._sync_tool_skills()
        if not was_initialized:
            logger.info(
                "Skill service initialized: {} file skills, {} tool skills",
                len(file_skills),
                len(tool_skills),
            )

    @staticmethod
    def _sync_tool_skills() -> list["AIToolDefinition"]:
        tool_service = _get_ai_tool_service()
        tools = tool_service.registry.list_tools()

        # Sync tool-based skills (file skills take priority on name
        # collision — register_tool_skill skips existing entries)
        for tool in tools:
            ai_skill_runtime.register_tool_skill(
                skill_name=tool.name,
                description=tool.description,
                tags=tool.tags,
            )
        return tools

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillMetadata"]:
        """Return all skills (tool + file) as contract-derived metadata."""

        self.ensure_initialized()
        tool_service = _get_ai_tool_service()

        tool_skills = [
            build_tool_skill_metadata(tool)
            for tool in tool_service.list_tool_specs(policy)
        ]
        file_skills = [
            build_file_skill_metadata(file_def)
            for file_def in ai_skill_runtime.list_file_skills()
        ]

        deduped_skills = {skill.name: skill for skill in tool_skills}
        for skill in file_skills:
            deduped_skills[skill.name] = skill
        return sorted(deduped_skills.values(), key=lambda s: s.name)

    def list_catalog(self) -> list["AISkillCatalogEntry"]:
        """Return the unified runtime catalog."""

        self.ensure_initialized()
        return ai_skill_runtime.list_catalog()

    def list_file_skills(self) -> list["AISkillFileDefinition"]:
        """Return only file-based skills."""

        self.ensure_initialized()
        return ai_skill_runtime.list_file_skills()

    def activate_skill_explicit(
        self,
        skill_name: str,
    ) -> "AISkillActivation | None":
        """Activate a skill by name (admin/test use)."""

        self.ensure_initialized()
        return ai_skill_runtime.activate_skill_explicit(skill_name)


ai_skill_service = AISkillService()


def _skill_sources(
    *,
    skills_dir: "Path | None",
    extra_sources: tuple["Path", ...],
) -> tuple["Path", ...]:
    primary = skills_dir or get_default_skills_directory()
    resolved = [primary.resolve(strict=False)]
    resolved.extend(source.resolve(strict=False) for source in extra_sources)
    return tuple(dict.fromkeys(resolved))


__all__ = ["AISkillService", "ai_skill_service"]
