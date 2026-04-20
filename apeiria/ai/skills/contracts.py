"""Helpers for deriving structured skill contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from apeiria.ai.skills.catalog import AISkillContract, AISkillDefinition

if TYPE_CHECKING:
    from apeiria.ai.skills.parser import AISkillFileDefinition
    from apeiria.ai.tools.models import AIToolSpec


def build_skill_definition(tool: "AIToolSpec") -> AISkillDefinition:
    """Map one tool spec into the product-facing contract shape."""

    return AISkillDefinition(
        skill_name=tool.name,
        description=tool.description,
        contract=AISkillContract(
            visibility=True,
            side_effect_level=_map_side_effect_level(tool),
            permission_source="global",
            idempotency="idempotent" if tool.concurrency_safe else "non_idempotent",
            fallback_behavior="degrade_to_text_reply",
        ),
        origin="tool",
        entry_mode="tool_backed",
        tags=tool.tags,
    )


def build_file_skill_definition(file_def: "AISkillFileDefinition") -> AISkillDefinition:
    """Map a file-based skill into the product-facing contract shape."""

    return AISkillDefinition(
        skill_name=file_def.skill_name,
        description=file_def.description,
        contract=AISkillContract(
            visibility=True,
            side_effect_level=_infer_file_skill_side_effect(file_def),
            permission_source="global",
            idempotency="idempotent",
            fallback_behavior="degrade_to_text_reply",
        ),
        origin="file",
        entry_mode=file_def.entry_mode,
        tags=file_def.tags,
    )


def _map_side_effect_level(
    tool: "AIToolSpec",
) -> Literal["read_only", "low_risk", "high_risk"]:
    if tool.read_only:
        return "read_only"
    if tool.risk_level == "high":
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
