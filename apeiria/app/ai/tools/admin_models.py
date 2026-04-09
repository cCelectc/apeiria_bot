"""Admin-facing tool and capability view models."""

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
