"""Person-profile admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.admin.audit import record_ai_admin_audit
from apeiria.ai.person.service import ai_person_profile_service

if TYPE_CHECKING:
    from apeiria.ai.person.models import (
        AIPersonMemoryPoint,
        AIPersonProfileDefinition,
    )


class PersonProfilesAdminMixin:
    """Admin CRUD for AI person profiles."""

    async def list_person_profiles(
        self,
        *,
        limit: int = 50,
    ) -> list["AIPersonProfileDefinition"]:
        return await ai_person_profile_service.list_profiles(limit=limit)

    async def get_person_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> "AIPersonProfileDefinition | None":
        return await ai_person_profile_service.get_profile(
            platform=platform,
            user_id=user_id,
        )

    async def update_person_profile(
        self,
        *,
        person_id: str,
        person_name: str | None = None,
        nickname: str | None = None,
        memory_points: "tuple[AIPersonMemoryPoint, ...] | None" = None,
        actor_username: str | None = None,
    ) -> "AIPersonProfileDefinition | None":
        result = await ai_person_profile_service.update_profile(
            person_id=person_id,
            person_name=person_name,
            nickname=nickname,
            memory_points=memory_points,
        )
        if result is not None:
            record_ai_admin_audit(
                "ai_person_profile_updated",
                actor_username=actor_username,
                detail=f"{result.person_id} {result.person_name}",
            )
        return result

    async def delete_person_profile(
        self,
        *,
        person_id: str,
        actor_username: str | None = None,
    ) -> bool:
        existing = await ai_person_profile_service.get_profile_by_id(
            person_id=person_id,
        )
        deleted = await ai_person_profile_service.delete_profile(
            person_id=person_id,
        )
        if deleted:
            record_ai_admin_audit(
                "ai_person_profile_deleted",
                actor_username=actor_username,
                detail=(
                    f"{existing.person_id} {existing.person_name}"
                    if existing is not None
                    else person_id
                ),
            )
        return deleted


__all__ = ["PersonProfilesAdminMixin"]
