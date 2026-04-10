"""Memory domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIMemoryType = Literal[
    "fact",
    "preference",
    "relationship",
    "episode",
    "summary",
    "operator_note",
]
AIMemoryExtractionAction = Literal["add", "update", "noop"]


@dataclass(frozen=True)
class AIMemoryExtractionCandidate:
    """One structured memory candidate produced by extraction."""

    memory_type: AIMemoryType
    content: str
    action: AIMemoryExtractionAction = "add"
    target_memory_id: str | None = None
    confidence: float = 0.7
    salience: float = 0.6


@dataclass(frozen=True)
class AIMemoryDefinition:
    """Pure memory item representation used by the AI domain."""

    memory_id: str
    memory_type: AIMemoryType
    subject_type: str
    subject_id: str
    content: str
    source_turn_id: str | None
    salience: float
    confidence: float
    last_recalled_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AIMemoryQuery:
    """Query payload for relevance-ranked memory retrieval."""

    subject_type: str
    subject_id: str
    query_text: str
    limit: int
