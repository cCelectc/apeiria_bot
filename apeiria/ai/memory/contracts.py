"""Public operation contracts for AI memory services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryKind,
        AIMemoryLayer,
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
    is_ignored: bool = False
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
