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
    "impression",
]
AIMemoryExtractionAction = Literal["add", "update", "noop"]
AISentimentPolarity = Literal["positive", "neutral", "negative", "playful"]


@dataclass(frozen=True)
class AIMessageSentiment:
    """Sentiment analysis result extracted alongside memory candidates."""

    polarity: AISentimentPolarity
    intensity: float  # 0.0-1.0


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
    source_message_id: str | None
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


@dataclass(frozen=True)
class AIMemoryExtractionResult:
    """Combined result of one LLM memory extraction call."""

    candidates: list[AIMemoryExtractionCandidate]
    sentiment: AIMessageSentiment
    self_introduction_name: str | None
