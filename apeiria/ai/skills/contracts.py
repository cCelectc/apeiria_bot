"""Helpers for deriving prompt-skill metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.skills.catalog import AISkillMetadata

if TYPE_CHECKING:
    from apeiria.ai.skills.parser import AISkillFileDefinition


def build_file_skill_metadata(
    file_def: "AISkillFileDefinition",
    *,
    loaded: bool = True,
    selectable_now: bool = True,
    error: str | None = None,
) -> AISkillMetadata:
    """Map a file-based skill into prompt-skill catalog metadata."""

    return AISkillMetadata(
        name=file_def.skill_name,
        description=file_def.description,
        origin="file",
        entry_mode=file_def.entry_mode,
        tags=file_def.tags,
        source_path=file_def.file_path,
        required_tools=file_def.tools,
        loaded=loaded,
        selectable_now=selectable_now,
        display_name=file_def.skill_name,
        display_description=file_def.description,
        error=error,
    )
