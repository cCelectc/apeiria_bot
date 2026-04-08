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
