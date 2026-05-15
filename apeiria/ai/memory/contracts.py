"""Public operation contracts for AI memory services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryKind,
        AIMemoryLayer,
        AIMemoryLifecycleState,
        AIMemoryUseMode,
    )


@dataclass(frozen=True)
class AIMemoryCreateInput:
    """Create payload for one structured memory item."""

    anchor_type: AIMemoryAnchorType
    anchor_id: str
    memory_layer: AIMemoryLayer
    memory_kind: AIMemoryKind
    content: str
    is_editable: bool = True
    lifecycle_state: AIMemoryLifecycleState = "active"
    default_use_mode: AIMemoryUseMode = "context"
    governance_reason: str | None = None
    source_message_id: str | None = None
    salience: float = 0.5
    confidence: float = 0.5


@dataclass(frozen=True)
class AIMemoryUpdateInput:
    """Update payload for one existing memory item."""

    content: str
    salience: float
    confidence: float
    source_message_id: str | None


@dataclass(frozen=True)
class AIMemoryStateUpdateInput:
    """Lifecycle update payload for one governed memory belief."""

    lifecycle_state: AIMemoryLifecycleState
    default_use_mode: AIMemoryUseMode | None = None
    governance_reason: str | None = None
