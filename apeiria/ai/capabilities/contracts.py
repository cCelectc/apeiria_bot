"""Capability contract value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

AICapabilityRiskLevel = Literal["low", "medium", "high"]


class AICapabilityKind(str, Enum):
    """First-version capability contract kinds."""

    EXECUTABLE = "executable"
    PROMPT_SKILL = "prompt_skill"


class AICapabilityOrigin(str, Enum):
    """Where a capability contract came from."""

    BUILTIN = "builtin"
    PLUGIN = "plugin"
    SKILL = "skill"


@dataclass(frozen=True)
class AICapabilitySafety:
    """Safety metadata shared by executable capabilities and prompt skills."""

    read_only: bool
    risk_level: AICapabilityRiskLevel
    concurrency_safe: bool
    timeout_seconds: float | None = None
    requires_operator_approval: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            msg = "capability timeout_seconds must be positive when provided"
            raise ValueError(msg)

    @property
    def mutates_state(self) -> bool:
        """Return whether this capability can change host or memory state."""

        return not self.read_only


@dataclass(frozen=True)
class AICapabilityContract:
    """Provider-neutral metadata for one AI-facing ability."""

    name: str
    kind: AICapabilityKind
    origin: AICapabilityOrigin
    description: str
    safety: AICapabilitySafety
    input_schema: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    display_name: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not self.input_schema:
            object.__setattr__(
                self,
                "input_schema",
                {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
