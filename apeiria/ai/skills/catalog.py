"""Catalog models for LLM-visible prompt skills."""

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
SkillOrigin = Literal["tool", "file"]


@dataclass(frozen=True)
class AISkillMetadata:
    """Product-facing prompt skill metadata for admin and catalog reads."""

    name: str
    description: str
    side_effect_level: SkillSideEffectLevel
    permission_source: SkillPermissionSource
    idempotent: bool
    fallback_behavior: str
    origin: SkillOrigin = "tool"
    entry_mode: str = "tool_backed"
    tags: tuple[str, ...] = ()
