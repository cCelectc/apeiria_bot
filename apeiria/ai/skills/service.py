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
        self._last_reload_errors: tuple[str, ...] = ()

    def ensure_initialized(
        self,
        *,
        skills_dir: "Path | None" = None,
        skill_sources: tuple["Path", ...] = (),
    ) -> None:
        """Load file-based skills once, or refresh source tracking when needed."""

        sources = _skill_sources(
            skills_dir=skills_dir,
            extra_sources=skill_sources,
        )
        if self._initialized and all(
            source in self._loaded_skill_sources for source in sources
        ):
            return

        self.reload_skills(
            skills_dir=skills_dir,
            skill_sources=skill_sources,
        )

    def reload_skills(
        self,
        *,
        skills_dir: "Path | None" = None,
        skill_sources: tuple["Path", ...] = (),
    ) -> tuple[str, ...]:
        """Fully rescan configured skill sources and replace runtime catalog."""

        sources = _skill_sources(
            skills_dir=skills_dir,
            extra_sources=skill_sources,
        )
        try:
            file_skills = load_skills_from_sources(sources)
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning("Skill reload failed")
            self._last_reload_errors = (str(exc),)
            self._initialized = True
            return self._last_reload_errors

        ai_skill_runtime.replace_file_skills(file_skills)
        self._loaded_skill_sources = set(sources)
        self._initialized = True
        self._last_reload_errors = ()
        logger.info(
            "Skill service reloaded: {} file skills",
            len(file_skills),
        )
        return self._last_reload_errors

    def list_skills(self) -> list["AISkillMetadata"]:
        """Return parsed prompt skills as product-facing metadata."""

        self.ensure_initialized()
        catalog_names = {item.skill_name for item in ai_skill_runtime.list_catalog()}
        last_error = (
            "\n".join(self._last_reload_errors) if self._last_reload_errors else None
        )
        file_skills = [
            build_file_skill_metadata(
                file_def,
                loaded=file_def.skill_name in catalog_names,
                selectable_now=file_def.skill_name in catalog_names,
                error=last_error,
            )
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
