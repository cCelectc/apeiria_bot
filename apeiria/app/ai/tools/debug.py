"""Advanced debug models for the tool boundary."""

from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class AIToolIntentPreview:
    """One planned tool intent visible to admin preview surfaces."""

    tool_name: str
    kind: str
    reason: str | None
    input_payload: object | None


__all__ = [
    "AICapabilityDefinition",
    "AICapabilityPreview",
    "AIToolIntentPreview",
]
