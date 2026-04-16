"""Person profile domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIPersonMemoryPointCategory = Literal[
    "preference",
    "fact",
    "relationship",
    "impression",
]


@dataclass(frozen=True)
class AIPersonMemoryPoint:
    """One durable person-level memory point."""

    category: AIPersonMemoryPointCategory
    content: str
    confidence: float
    source_message_id: str | None = None


@dataclass(frozen=True)
class AIPersonProfileDefinition:
    """Structured profile for one known user."""

    person_id: str
    platform: str
    user_id: str
    person_name: str | None
    nickname: str | None
    name_reason: str | None
    memory_points: tuple[AIPersonMemoryPoint, ...]
    is_known: bool
    know_since: datetime | None
    last_interaction: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AIPersonPromptProfile:
    """Prompt-facing person profile snapshot."""

    person_id: str
    preferred_name: str | None
    prompt_lines: tuple[str, ...]
    relationship_score: float
    mood_tags: tuple[str, ...]
