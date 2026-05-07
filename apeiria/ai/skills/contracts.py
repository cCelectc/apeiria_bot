"""Helpers for deriving prompt-skill metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeiria.ai.skills.catalog import AISkillMetadata

if TYPE_CHECKING:
    from apeiria.ai.capabilities import AICapabilityContract
    from apeiria.ai.skills.parser import AISkillFileDefinition


def build_skill_metadata(contract: AICapabilityContract) -> AISkillMetadata:
    """Map one executable capability contract into skill catalog metadata."""

    return AISkillMetadata(
        name=contract.name,
        description=contract.description,
        side_effect_level=_map_side_effect_level(contract),
        permission_source="global",
        idempotent=contract.safety.concurrency_safe,
        fallback_behavior="degrade_to_text_reply",
        origin="tool",
        entry_mode="tool_backed",
        tags=contract.tags,
    )


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


def _map_side_effect_level(
    contract: "AICapabilityContract",
) -> Literal["read_only", "low_risk", "high_risk"]:
    if contract.safety.read_only:
        return "read_only"
    if contract.safety.risk_level == "high":
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
