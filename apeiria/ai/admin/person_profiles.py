"""Person-profile admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

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
        async with get_session() as session:
            return await ai_person_profile_service.list_profiles(session, limit=limit)

    async def get_person_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> "AIPersonProfileDefinition | None":
        async with get_session() as session:
            return await ai_person_profile_service.get_profile(
                session,
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
        async with get_session() as session:
            result = await ai_person_profile_service.update_profile(
                session,
                person_id=person_id,
                person_name=person_name,
                nickname=nickname,
                memory_points=memory_points,
            )
            if result is not None:
                await session.commit()
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
        async with get_session() as session:
            existing = await ai_person_profile_service.get_profile_by_id(
                session,
                person_id=person_id,
            )
            deleted = await ai_person_profile_service.delete_profile(
                session,
                person_id=person_id,
            )
            if deleted:
                await session.commit()
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
