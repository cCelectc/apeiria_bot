"""Relationship admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.relationship.service import ai_relationship_service

if TYPE_CHECKING:
    from apeiria.app.ai.relationship.models import (
        AIRelationshipEvent,
        AIRelationshipState,
    )


class RelationshipsAdminMixin:
    """Admin read/mutation for AI relationship states and events."""

    async def list_relationships(
        self,
        *,
        limit: int = 50,
    ) -> list["AIRelationshipState"]:
        async with get_session() as session:
            return await ai_relationship_service.list_states(session, limit=limit)

    async def get_relationship_state(
        self,
        *,
        platform: str,
        user_id: str,
        group_id: str | None = None,
    ) -> "AIRelationshipState":
        async with get_session() as session:
            return await ai_relationship_service.get_state(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )

    async def list_relationship_events(
        self,
        *,
        platform: str,
        user_id: str,
        group_id: str | None = None,
        limit: int = 20,
    ) -> list["AIRelationshipEvent"]:
        async with get_session() as session:
            return await ai_relationship_service.list_events_for_target(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
                limit=limit,
            )

    async def set_relationship_score(
        self,
        *,
        platform: str,
        user_id: str,
        score: float,
        group_id: str | None = None,
        actor_username: str | None = None,
    ) -> "AIRelationshipState":
        async with get_session() as session:
            state = await ai_relationship_service.set_manual_score(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
                score=score,
            )
            await session.commit()
            record_ai_admin_audit(
                "ai_relationship_score_updated",
                actor_username=actor_username,
                detail=(
                    f"{platform}:{group_id or '__private__'}:{user_id} score={score}"
                ),
            )
            return state


__all__ = ["RelationshipsAdminMixin"]
