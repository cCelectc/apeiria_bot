"""Relationship state storage and emotion projection service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipState,
    EmotionProjection,
)
from apeiria.app.ai.relationship.scope import build_affinity_scope_key
from apeiria.app.ai.relationship.scoring import (
    apply_relationship_delta,
    project_emotion,
)
from apeiria.infra.db.models import AIAffinity

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AIRelationshipService:
    """Relationship persistence and emotion projection service."""

    async def get_state(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load or initialize relationship state."""

        scope_key = build_affinity_scope_key(group_id)
        result = await session.execute(
            select(AIAffinity).where(
                AIAffinity.platform == platform,
                AIAffinity.scope_key == scope_key,
                AIAffinity.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = AIAffinity(
                affinity_id=f"aff_{uuid4().hex}",
                platform=platform,
                group_id=group_id,
                scope_key=scope_key,
                user_id=user_id,
                score=0.0,
                mood_tags_json="[]",
                last_event_at=_utcnow_naive(),
            )
            session.add(row)
            await session.flush()
        return self._to_state(row)

    async def apply_delta(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        delta: AIRelationshipDelta,
    ) -> AIRelationshipState:
        """Apply one deterministic delta and persist the updated state."""

        scope_key = build_affinity_scope_key(group_id)
        result = await session.execute(
            select(AIAffinity).where(
                AIAffinity.platform == platform,
                AIAffinity.scope_key == scope_key,
                AIAffinity.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            state = await self.get_state(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
            result = await session.execute(
                select(AIAffinity).where(AIAffinity.affinity_id == state.affinity_id)
            )
            row = result.scalar_one()
        else:
            state = self._to_state(row)

        updated = apply_relationship_delta(state, delta)
        row.score = updated.score
        row.mood_tags_json = json.dumps(updated.mood_tags, ensure_ascii=False)
        row.last_event_at = _utcnow_naive()
        await session.flush()
        return self._to_state(row)

    async def set_manual_score(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        score: float,
    ) -> AIRelationshipState:
        """Persist an operator override for relationship score."""

        state = await self.get_state(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        result = await session.execute(
            select(AIAffinity).where(AIAffinity.affinity_id == state.affinity_id)
        )
        row = result.scalar_one()
        row.score = max(-1.0, min(1.0, score))
        row.last_event_at = _utcnow_naive()
        await session.flush()
        return self._to_state(row)

    async def project_state(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> EmotionProjection:
        """Build the current emotion projection for one user within a scene."""

        state = await self.get_state(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        return project_emotion(state)

    @staticmethod
    def _to_state(row: AIAffinity) -> AIRelationshipState:
        mood_tags = tuple(json.loads(row.mood_tags_json or "[]"))
        last_event_at = (
            row.last_event_at.replace(tzinfo=timezone.utc)
            if row.last_event_at.tzinfo is None
            else row.last_event_at
        )
        return AIRelationshipState(
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            score=row.score,
            mood_tags=mood_tags,
            last_event_at=last_event_at,
        )


ai_relationship_service = AIRelationshipService()
