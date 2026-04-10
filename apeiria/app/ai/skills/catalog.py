"""Catalog models for LLM-visible skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SkillSideEffectLevel = Literal["read_only", "low_risk", "high_risk"]
SkillPermissionSource = Literal[
    "global",
    "group",
    "conversation",
    "persona",
]
SkillIdempotency = Literal["idempotent", "non_idempotent"]


@dataclass(frozen=True)
class AISkillContract:
    """Explicit contract attached to one visible skill."""

    visibility: bool
    side_effect_level: SkillSideEffectLevel
    permission_source: SkillPermissionSource
    idempotency: SkillIdempotency
    fallback_behavior: str


@dataclass(frozen=True)
class AISkillDefinition:
    """Product-facing skill definition built on top of legacy tool specs."""

    skill_name: str
    description: str
    contract: AISkillContract
