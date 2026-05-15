"""Schema models for AI profile routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.profile import AIProfileDefinition

AIProfileNameSourceValue = Literal[
    "manual",
    "self_introduced",
    "platform",
    "inferred",
]
AIProfileNameVisibilityValue = Literal[
    "private_only",
    "public_allowed",
    "disabled",
]


class AIProfileItem(BaseModel):
    profile_id: str
    platform: str
    user_id: str
    display_name: str | None = None
    preferred_name: str | None = None
    name_source: str | None = None
    name_visibility: str
    profile_enabled: bool
    last_interaction_at: str
    created_at: str
    updated_at: str


class AIProfileUpdateRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    preferred_name: str | None = Field(default=None, max_length=128)
    name_source: AIProfileNameSourceValue | None = None
    name_visibility: AIProfileNameVisibilityValue | None = None
    profile_enabled: bool | None = None


def to_ai_profile_item(
    item: "AIProfileDefinition",
) -> AIProfileItem:
    return AIProfileItem(
        profile_id=item.profile_id,
        platform=item.platform,
        user_id=item.user_id,
        display_name=item.display_name,
        preferred_name=item.preferred_name,
        name_source=item.name_source,
        name_visibility=item.name_visibility,
        profile_enabled=item.profile_enabled,
        last_interaction_at=item.last_interaction_at.isoformat(),
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
