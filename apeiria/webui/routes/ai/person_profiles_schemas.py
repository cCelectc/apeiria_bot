"""Schema models for AI person-profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.person import AIPersonProfileDefinition


class AIPersonMemoryPointItem(BaseModel):
    category: str
    content: str
    confidence: float
    source_message_id: str | None = None


class AIPersonProfileItem(BaseModel):
    person_id: str
    platform: str
    user_id: str
    person_name: str | None = None
    nickname: str | None = None
    name_reason: str | None = None
    memory_points: list[AIPersonMemoryPointItem] = []
    is_known: bool
    know_since: str | None = None
    last_interaction: str
    created_at: str
    updated_at: str


class AIPersonProfileUpdateRequest(BaseModel):
    person_id: str = Field(min_length=1, max_length=64)
    person_name: str | None = Field(default=None, max_length=128)
    nickname: str | None = Field(default=None, max_length=128)
    memory_points: list[AIPersonMemoryPointItem] | None = None


def to_ai_person_profile_item(
    item: "AIPersonProfileDefinition",
) -> AIPersonProfileItem:
    return AIPersonProfileItem(
        person_id=item.person_id,
        platform=item.platform,
        user_id=item.user_id,
        person_name=item.person_name,
        nickname=item.nickname,
        name_reason=item.name_reason,
        memory_points=[
            AIPersonMemoryPointItem(
                category=point.category,
                content=point.content,
                confidence=point.confidence,
                source_message_id=point.source_message_id,
            )
            for point in item.memory_points
        ],
        is_known=item.is_known,
        know_since=item.know_since.isoformat() if item.know_since else None,
        last_interaction=item.last_interaction.isoformat(),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
