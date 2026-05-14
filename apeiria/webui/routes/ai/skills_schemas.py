"""Schema models for AI prompt-skill routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.ai.skills import AISkillMetadata


class AISkillItem(BaseModel):
    name: str
    description: str
    display_name: str
    display_description: str


def _skill_display_name(skill_name: str) -> str:
    return skill_name


def _skill_display_description(skill_name: str, fallback: str) -> str:
    del skill_name
    return fallback


def to_ai_skill_item(item: "AISkillMetadata") -> AISkillItem:
    return AISkillItem(
        name=item.name,
        description=item.description,
        display_name=_skill_display_name(item.name),
        display_description=_skill_display_description(
            item.name,
            item.description,
        ),
    )


__all__ = ["AISkillItem", "to_ai_skill_item"]
