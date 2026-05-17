"""Helpers for deriving prompt-skill metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.skills.catalog import AISkillMetadata

if TYPE_CHECKING:
    from apeiria.ai.skills.parser import AISkillFileDefinition


def build_file_skill_metadata(
    file_def: "AISkillFileDefinition",
) -> AISkillMetadata:
    """Map a file-based skill into prompt-skill catalog metadata."""

    return AISkillMetadata(
        name=file_def.skill_name,
        description=file_def.description,
        origin="file",
        entry_mode=file_def.entry_mode,
        tags=file_def.tags,
    )
