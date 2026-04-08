"""Tool domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIToolRiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class AIToolSpec:
    """Pure tool declaration visible to the AI orchestration layer."""

    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: AIToolRiskLevel = "low"
    is_capability_bridge: bool = False


@dataclass(frozen=True)
class AIToolPolicy:
    """Pure tool access policy for one AI scene."""

    allowed_tool_names: set[str] | None = None
    denied_tool_names: set[str] = field(default_factory=set)
    allow_high_risk_tools: bool = False
    allow_capability_bridge: bool = False


@dataclass(frozen=True)
class AIToolPolicyDecision:
    """Decision returned by tool policy evaluation."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class AINoneBotCapabilityRequest:
    """Structured request for a whitelist-based NoneBot capability bridge."""

    capability_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIToolExecutionView:
    """Pure execution record view."""

    execution_id: str
    conversation_id: str
    tool_name: str
    status: str
    input_json: str | None
    output_json: str | None
    created_at: datetime
