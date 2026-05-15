"""Profile domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIProfileNameSource = Literal["manual", "self_introduced", "platform", "inferred"]
AIProfileNameVisibility = Literal["private_only", "public_allowed", "disabled"]


class _AIProfileUnsetValue:
    """Sentinel for profile update fields that were not provided."""

    __slots__ = ()


AIProfileUnset: Final = _AIProfileUnsetValue()
AIProfileNullableTextUpdate = str | None | _AIProfileUnsetValue
AIProfileNameSourceUpdate = AIProfileNameSource | None | _AIProfileUnsetValue


@dataclass(frozen=True)
class AIProfileDefinition:
    """Stable user-facing profile metadata."""

    profile_id: str
    platform: str
    user_id: str
    display_name: str | None
    preferred_name: str | None
    name_source: AIProfileNameSource | None
    name_visibility: AIProfileNameVisibility
    profile_enabled: bool
    last_interaction_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AIProfileUpdateInput:
    """Profile metadata update command."""

    display_name: AIProfileNullableTextUpdate = AIProfileUnset
    preferred_name: AIProfileNullableTextUpdate = AIProfileUnset
    name_source: AIProfileNameSourceUpdate = AIProfileUnset
    name_visibility: AIProfileNameVisibility | None = None
    profile_enabled: bool | None = None


@dataclass(frozen=True)
class AIProfileCard:
    """Prompt-facing runtime projection for one user profile."""

    profile_id: str
    lines: tuple[str, ...]
    source_refs: tuple[str, ...]
    generated_at: datetime
