"""Memory domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIMemoryAnchorType = Literal["scene", "participant", "user"]
AIMemoryLayer = Literal["summary", "long_term", "knowledge", "operator"]
AIMemoryKind = Literal[
    "fact",
    "preference",
    "relationship",
    "note",
]
AIMemoryExtractionAction = Literal["add", "update", "noop"]


@dataclass(frozen=True)
class AIMemoryExtractionCandidate:
    """One structured memory candidate produced by extraction."""

    memory_kind: AIMemoryKind
    content: str
    action: AIMemoryExtractionAction = "add"
    target_memory_id: str | None = None
    confidence: float = 0.7
    salience: float = 0.6


@dataclass(frozen=True)
class AIMemoryDefinition:
    """Pure memory item representation used by the AI domain."""

    memory_id: str
    anchor_type: AIMemoryAnchorType
    anchor_id: str
    memory_layer: AIMemoryLayer
    memory_kind: AIMemoryKind
    content: str
    is_editable: bool
    is_ignored: bool
    source_turn_id: str | None
    salience: float
    confidence: float
    last_recalled_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AIMemoryQuery:
    """Query payload for relevance-ranked memory retrieval."""

    anchor_type: AIMemoryAnchorType
    anchor_id: str
    query_text: str
    limit: int
    memory_layer: AIMemoryLayer | None = None
    memory_kind: AIMemoryKind | None = None
