"""Helpers for deriving prompt-skill metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeiria.ai.skills.catalog import AISkillMetadata
from apeiria.ai.tools.models import AIToolLevel

if TYPE_CHECKING:
    from apeiria.ai.skills.parser import AISkillFileDefinition
    from apeiria.ai.tools.models import AIToolDefinition


def build_tool_skill_metadata(tool: "AIToolDefinition") -> AISkillMetadata:
    """Map one first-class tool into skill catalog metadata."""

    return AISkillMetadata(
        name=tool.name,
        description=tool.description,
        side_effect_level=_map_tool_side_effect_level(tool),
        permission_source="global",
        idempotent=tool.required_level is AIToolLevel.READ,
        fallback_behavior="degrade_to_text_reply",
        origin="tool",
        entry_mode="tool_backed",
        tags=tool.tags,
    )


build_skill_metadata = build_tool_skill_metadata


def build_file_skill_metadata(
    file_def: "AISkillFileDefinition",
) -> AISkillMetadata:
    """Map a file-based skill into prompt-skill catalog metadata."""

    return AISkillMetadata(
        name=file_def.skill_name,
        description=file_def.description,
        side_effect_level=_infer_file_skill_side_effect(file_def),
        permission_source="global",
        idempotent=True,
        fallback_behavior="degrade_to_text_reply",
        origin="file",
        entry_mode=file_def.entry_mode,
        tags=file_def.tags,
    )


def _map_tool_side_effect_level(
    tool: "AIToolDefinition",
) -> Literal["read_only", "low_risk", "high_risk"]:
    if tool.required_level is AIToolLevel.READ:
        return "read_only"
    if tool.required_level in {AIToolLevel.HOST, AIToolLevel.ADMIN}:
        return "high_risk"
    return "low_risk"


def _infer_file_skill_side_effect(
    file_def: "AISkillFileDefinition",
) -> Literal["read_only", "low_risk", "high_risk"]:
    """Infer side-effect level from file skill permissions."""

    write_perms = {"write_memory", "update_memory", "delete_memory", "send_message"}
    if any(perm in write_perms for perm in file_def.permissions):
        return "low_risk"
    return "read_only"
