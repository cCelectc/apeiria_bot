"""Profile storage and prompt-card service."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from apeiria.ai.profile.models import (
    AIProfileCard,
    AIProfileDefinition,
    AIProfileNameSource,
    AIProfileNameVisibility,
    AIProfileUnset,
    AIProfileUpdateInput,
)
from apeiria.ai.profile.repository import ProfileRepository, ProfileRow, utcnow

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMemoryDefinition

_PROFILE_MEMORY_LABELS: dict[str, str] = {
    "preference": "沟通偏好",
    "fact": "稳定事实",
    "note": "档案备注",
    "impression": "印象",
}
_MAX_PROFILE_CARD_MEMORY_LINES = 4


class AIProfileService:
    """Persistence and runtime projection for user-facing profiles."""

    def __init__(
        self,
        *,
        repository: ProfileRepository | None = None,
    ) -> None:
        self._repository = repository or ProfileRepository()

    async def get_profile_by_id(
        self,
        *,
        profile_id: str,
    ) -> AIProfileDefinition | None:
        row = await self._repository.get_profile_row_by_id(profile_id=profile_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def get_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> AIProfileDefinition | None:
        row = await self._repository.get_profile_row(platform=platform, user_id=user_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> ProfileRow:
        return await self._repository.ensure_profile(platform=platform, user_id=user_id)

    async def list_profiles(
        self,
        *,
        limit: int = 50,
    ) -> list[AIProfileDefinition]:
        rows = await self._repository.list_profile_rows(limit=limit)
        return [self._to_definition(row) for row in rows]

    async def update_profile(
        self,
        *,
        profile_id: str,
        update_input: AIProfileUpdateInput,
    ) -> AIProfileDefinition | None:
        row = await self._repository.get_profile_row_by_id(profile_id=profile_id)
        if row is None:
            return None
        if update_input.display_name is not AIProfileUnset:
            display_name = update_input.display_name
            row.display_name = (
                display_name.strip() if isinstance(display_name, str) else None
            )
        if update_input.preferred_name is not AIProfileUnset:
            preferred_name = update_input.preferred_name
            row.preferred_name = (
                preferred_name.strip() if isinstance(preferred_name, str) else None
            )
        if update_input.name_source is not AIProfileUnset:
            name_source = update_input.name_source
            row.name_source = (
                cast("AIProfileNameSource", name_source)
                if isinstance(name_source, str)
                else None
            )
        if update_input.name_visibility is not None:
            row.name_visibility = update_input.name_visibility
        if update_input.profile_enabled is not None:
            row.profile_enabled = update_input.profile_enabled
        row.updated_at = utcnow()
        await self._repository.update_profile_row(row)
        return self._to_definition(row)

    async def delete_profile(
        self,
        *,
        profile_id: str,
    ) -> bool:
        return await self._repository.delete_profile(profile_id=profile_id)

    async def ingest_message(
        self,
        *,
        platform: str,
        user_id: str,
        scene_type: str,
        self_introduction_name: str | None = None,
    ) -> AIProfileDefinition | None:
        """Update profile metadata from high-confidence profile signals."""

        row = await self._repository.get_profile_row(
            platform=platform,
            user_id=user_id,
        )
        if row is None and not self_introduction_name:
            return None
        if row is None:
            row = await self.ensure_profile(platform=platform, user_id=user_id)

        now = utcnow()
        row.last_interaction_at = now
        row.updated_at = now
        if self_introduction_name:
            row.preferred_name = self_introduction_name
            row.display_name = row.display_name or self_introduction_name
            row.name_source = "self_introduced"
            row.name_visibility = (
                "private_only" if scene_type == "private" else "public_allowed"
            )
        await self._repository.update_profile_row(row)
        return self._to_definition(row)

    async def build_profile_card(
        self,
        *,
        platform: str,
        user_id: str,
        scene_type: str,
        memories: tuple["AIMemoryDefinition", ...] = (),
    ) -> AIProfileCard | None:
        """Build a prompt-ready runtime profile card."""

        profile = await self.get_profile(platform=platform, user_id=user_id)
        if profile is None or not profile.profile_enabled:
            return None

        lines: list[str] = []
        source_refs: list[str] = []
        if (
            _name_visible(profile.name_visibility, scene_type)
            and profile.preferred_name
        ):
            lines.append(f"- 首选名称: {profile.preferred_name}")
        elif profile.display_name:
            lines.append(f"- 显示名称: {profile.display_name}")

        memory_line_count = 0
        for memory in memories:
            if not _memory_belongs_to_profile(memory, user_id):
                continue
            label = _PROFILE_MEMORY_LABELS.get(memory.memory_kind)
            if label is None:
                continue
            lines.append(f"- {label}: {memory.content}")
            source_refs.append(memory.memory_id)
            memory_line_count += 1
            if memory_line_count >= _MAX_PROFILE_CARD_MEMORY_LINES:
                break

        if not lines:
            return None
        return AIProfileCard(
            profile_id=profile.profile_id,
            lines=tuple(lines),
            source_refs=tuple(source_refs),
            generated_at=utcnow(),
        )

    @staticmethod
    def _to_definition(row: ProfileRow) -> AIProfileDefinition:
        return AIProfileDefinition(
            profile_id=row.profile_id,
            platform=row.platform,
            user_id=row.user_id,
            display_name=row.display_name,
            preferred_name=row.preferred_name,
            name_source=row.name_source,
            name_visibility=row.name_visibility,
            profile_enabled=row.profile_enabled,
            last_interaction_at=row.last_interaction_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _name_visible(
    visibility: AIProfileNameVisibility,
    scene_type: str,
) -> bool:
    if visibility == "disabled":
        return False
    return visibility != "private_only" or scene_type == "private"


def _memory_belongs_to_profile(memory: "AIMemoryDefinition", user_id: str) -> bool:
    if memory.anchor_type == "user":
        return memory.anchor_id == user_id
    return memory.anchor_type == "participant"
