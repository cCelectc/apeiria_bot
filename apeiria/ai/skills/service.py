"""Product-facing service for file-based prompt skills."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.skills.contracts import build_file_skill_metadata
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


class AISkillService:
    """Skill service for parsed ``SKILL.md`` prompt/workflow skills."""

    def __init__(self) -> None:
        self._initialized = False
        self._loaded_skill_sources: set[Path] = set()

    def ensure_initialized(
        self,
        *,
        skills_dir: "Path | None" = None,
        skill_sources: tuple["Path", ...] = (),
    ) -> None:
        """Load file-based skills.

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

        if not was_initialized:
            logger.info(
                "Skill service initialized: {} file skills",
                len(file_skills),
            )

    def list_skills(self) -> list["AISkillMetadata"]:
        """Return parsed prompt skills as product-facing metadata."""

        self.ensure_initialized()
        file_skills = [
            build_file_skill_metadata(file_def)
            for file_def in ai_skill_runtime.list_file_skills()
        ]
        return sorted(file_skills, key=lambda s: s.name)

    def list_catalog(self) -> list["AISkillCatalogEntry"]:
        """Return the prompt skill runtime catalog."""

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
