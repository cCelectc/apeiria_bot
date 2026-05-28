"""Profile admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.diagnostics.audit import record_ai_admin_audit
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.profile import (
        AIProfileDefinition,
        AIProfileUpdateInput,
    )


class ProfilesAdminMixin:
    """Admin CRUD for AI user profiles."""

    async def list_user_profiles(
        self,
        *,
        limit: int = 50,
    ) -> list["AIProfileDefinition"]:
        return await ai_wiring.profile_service.list_profiles(limit=limit)

    async def get_user_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> "AIProfileDefinition | None":
        return await ai_wiring.profile_service.get_profile(
            platform=platform,
            user_id=user_id,
        )

    async def update_user_profile(
        self,
        *,
        profile_id: str,
        update_input: "AIProfileUpdateInput",
        actor_username: str | None = None,
    ) -> "AIProfileDefinition | None":
        result = await ai_wiring.profile_service.update_profile(
            profile_id=profile_id,
            update_input=update_input,
        )
        if result is not None:
            record_ai_admin_audit(
                "ai_profile_updated",
                actor_username=actor_username,
                detail=f"{result.profile_id} {result.preferred_name}",
            )
        return result

    async def delete_user_profile(
        self,
        *,
        profile_id: str,
        actor_username: str | None = None,
    ) -> bool:
        existing = await ai_wiring.profile_service.get_profile_by_id(
            profile_id=profile_id,
        )
        deleted = await ai_wiring.profile_service.delete_profile(
            profile_id=profile_id,
        )
        if deleted:
            record_ai_admin_audit(
                "ai_profile_deleted",
                actor_username=actor_username,
                detail=(
                    f"{existing.profile_id} {existing.preferred_name}"
                    if existing is not None
                    else profile_id
                ),
            )
        return deleted


__all__ = ["ProfilesAdminMixin"]
