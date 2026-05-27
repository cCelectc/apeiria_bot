"""Schema models for AI prompt-skill routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.ai.skills.catalog import AISkillMetadata


class AISkillItem(BaseModel):
    name: str
    description: str
    display_name: str
    display_description: str
    entry_mode: str
    tags: list[str]
    source_path: str
    required_tools: list[str]
    loaded: bool
    selectable_now: bool
    error: str | None = None


def to_ai_skill_item(item: "AISkillMetadata") -> AISkillItem:
    return AISkillItem(
        name=item.name,
        description=item.description,
        display_name=item.display_name or item.name,
        display_description=item.display_description or item.description,
        entry_mode=item.entry_mode,
        tags=list(item.tags),
        source_path=item.source_path,
        required_tools=list(item.required_tools),
        loaded=item.loaded,
        selectable_now=item.selectable_now,
        error=item.error,
    )


__all__ = [
    "AISkillItem",
    "to_ai_skill_item",
]
