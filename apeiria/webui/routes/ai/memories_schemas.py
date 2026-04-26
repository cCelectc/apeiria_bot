"""Schema models for AI memory routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition


class AIMemoryItem(BaseModel):
    memory_id: str
    anchor_type: str
    anchor_id: str
    memory_layer: str
    memory_kind: str
    content: str
    is_editable: bool
    is_ignored: bool
    source_message_id: str | None = None
    salience: float
    confidence: float
    last_recalled_at: str | None = None
    created_at: str


class AIMemoryCreateRequest(BaseModel):
    memory_layer: Literal["long_term", "knowledge", "operator"]
    memory_kind: Literal["fact", "preference", "relationship", "note"]
    anchor_type: Literal["scene", "participant", "user"]
    anchor_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=10000)
    salience: float = Field(default=0.6, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class AIMemoryUpdateRequest(BaseModel):
    memory_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=10000)
    salience: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class AIMemoryDeleteResult(BaseModel):
    deleted: bool


class AIMemoryBulkActionRequest(BaseModel):
    memory_ids: list[str] = Field(min_length=1, max_length=100)


class AIMemoryBulkIgnoreRequest(BaseModel):
    memory_ids: list[str] = Field(min_length=1, max_length=100)
    ignored: bool = True


class AIMemoryBulkActionResult(BaseModel):
    affected: int


class AIMemoryToggleIgnoredRequest(BaseModel):
    memory_id: str = Field(min_length=1, max_length=64)


def to_ai_memory_item(item: "AIMemoryDefinition") -> AIMemoryItem:
    return AIMemoryItem(
        memory_id=item.memory_id,
        anchor_type=item.anchor_type,
        anchor_id=item.anchor_id,
        memory_layer=item.memory_layer,
        memory_kind=item.memory_kind,
        content=item.content,
        is_editable=item.is_editable,
        is_ignored=item.is_ignored,
        source_message_id=item.source_message_id,
        salience=item.salience,
        confidence=item.confidence,
        last_recalled_at=(
            item.last_recalled_at.isoformat() if item.last_recalled_at else None
        ),
        created_at=item.created_at.isoformat(),
    )
