"""Advanced debug models for the skill boundary."""

from __future__ import annotations

from dataclasses import dataclass

from apeiria.app.ai.skills.models import AIToolExecutionView as AISkillExecutionView


@dataclass(frozen=True)
class AICapabilityPreview:
    """Preview result for one capability under the current scene policy."""

    capability_name: str
    registered: bool
    allowed: bool
    reason: str
    allow_capability_bridge: bool
    execution_enabled: bool


@dataclass(frozen=True)
class AICapabilityDefinition:
    """One registered capability entry visible to admin surfaces."""

    capability_name: str
    bound_tool_name: str


__all__ = [
    "AICapabilityDefinition",
    "AICapabilityPreview",
    "AISkillExecutionView",
]
