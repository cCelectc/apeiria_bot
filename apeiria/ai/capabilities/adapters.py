"""Adapters for capability contract read models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .bindings import (
    AICapabilityBinding,
    create_prompt_skill_binding,
)
from .contracts import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilityRiskLevel,
    AICapabilitySafety,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.ai.skills.catalog import SkillSideEffectLevel
    from apeiria.ai.skills.contracts import AISkillMetadata
    from apeiria.ai.skills.parser import AISkillFileDefinition


def capability_contract_from_skill_definition(
    skill: "AISkillMetadata",
    *,
    load_prompt: "Callable[[], str]",
    required_capabilities: tuple[str, ...] = (),
) -> tuple[AICapabilityContract, AICapabilityBinding]:
    """Convert one catalog skill definition to a prompt-skill capability."""

    contract = AICapabilityContract(
        name=skill.name,
        kind=AICapabilityKind.PROMPT_SKILL,
        origin=AICapabilityOrigin.SKILL,
        description=skill.description,
        safety=AICapabilitySafety(
            read_only=skill.side_effect_level == "read_only",
            risk_level=_risk_from_skill_side_effect(skill.side_effect_level),
            concurrency_safe=skill.idempotent,
        ),
        tags=skill.tags,
    )
    return contract, create_prompt_skill_binding(
        contract_name=skill.name,
        binding_key=f"prompt:{skill.name}",
        load_prompt=load_prompt,
        required_capabilities=required_capabilities,
    )


def capability_contract_from_skill_file(
    skill: "AISkillFileDefinition",
) -> tuple[AICapabilityContract, AICapabilityBinding]:
    """Convert one parsed SKILL.md record to a prompt-skill capability."""

    contract = AICapabilityContract(
        name=skill.skill_name,
        kind=AICapabilityKind.PROMPT_SKILL,
        origin=AICapabilityOrigin.SKILL,
        description=skill.description,
        safety=AICapabilitySafety(
            read_only=True,
            risk_level="low",
            concurrency_safe=True,
        ),
        tags=skill.tags,
        version=skill.version,
    )
    return contract, create_prompt_skill_binding(
        contract_name=skill.skill_name,
        binding_key=f"prompt:{skill.skill_name}",
        load_prompt=lambda: skill.body_markdown,
        required_capabilities=skill.tools,
    )


def _risk_from_skill_side_effect(
    side_effect_level: "SkillSideEffectLevel",
) -> AICapabilityRiskLevel:
    if side_effect_level == "high_risk":
        return "high"
    if side_effect_level == "low_risk":
        return "medium"
    return "low"
