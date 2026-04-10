"""Helpers for deriving structured skill contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.skills.catalog import AISkillContract, AISkillDefinition

if TYPE_CHECKING:
    from apeiria.app.ai.skills.models import AIToolSpec


def build_skill_definition(tool: "AIToolSpec") -> AISkillDefinition:
    """Map one skill spec into the product-facing contract shape."""

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
    )


def _map_side_effect_level(tool: "AIToolSpec") -> str:
    if tool.read_only:
        return "read_only"
    if tool.risk_level == "high":
        return "high_risk"
    return "low_risk"
