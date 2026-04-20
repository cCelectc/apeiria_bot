"""Relationship state storage and emotion projection service."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.ai.relationship.models import (
    AIRelationshipDelta,
    AIRelationshipEvent,
    AIRelationshipEventType,
    AIRelationshipState,
    EmotionProjection,
)
from apeiria.ai.relationship.scope import build_affinity_scope_key
from apeiria.ai.relationship.scoring import (
    apply_inactivity_decay,
    apply_relationship_delta,
    project_emotion,
)
from apeiria.db.models import (
    AIAffinity,
)
from apeiria.db.models import (
    AIRelationshipEvent as AIRelationshipEventRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AIRelationshipService:
    """Relationship persistence and emotion projection service."""

    async def get_state_snapshot(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> tuple[float, tuple[str, ...]]:
        """Return a compact relationship snapshot for adjacent prompt systems."""

        state = await self.get_effective_state(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        return state.score, state.mood_tags

    async def get_state(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load or initialize relationship state."""

        row = await self._find_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._to_state(row)

    async def get_effective_state(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        """Load one relationship state with read-time decay applied in memory."""

        row = await self._find_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return self._build_default_state(
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )
        return self._build_effective_state(row)

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

        row = await self._get_or_create_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        state = await self._persist_inactivity_decay(session, row)

        updated = apply_relationship_delta(state, delta)
        now = _utcnow_naive()
        row.score = updated.score
        row.mood_tags_json = self._serialize_mood_tags(updated.mood_tags)
        row.last_event_at = now
        row.last_decay_at = None
        await self._record_event(
            session,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type=delta.event_type,
            score_delta=updated.score - state.score,
            score_after=updated.score,
            mood_tag=delta.mood_tag,
            reason=delta.reason,
            created_at=now,
        )
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

        row = await self._get_or_create_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        state = await self._persist_inactivity_decay(session, row)
        now = _utcnow_naive()
        next_score = max(-1.0, min(1.0, score))
        row.score = next_score
        row.last_event_at = now
        row.last_decay_at = None
        await self._record_event(
            session,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type="manual",
            score_delta=next_score - state.score,
            score_after=next_score,
            mood_tag=None,
            reason="manual score override",
            created_at=now,
        )
        await session.flush()
        return self._to_state(row)

    async def list_states(
        self,
        session: AsyncSession,
        *,
        limit: int,
    ) -> list[AIRelationshipState]:
        """List recent relationship states for owner-facing management."""

        result = await session.execute(
            select(AIAffinity)
            .order_by(AIAffinity.last_event_at.desc(), AIAffinity.id.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [self._to_state(row) for row in rows]

    async def list_events_for_target(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent events for one relationship target."""

        row = await self._find_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return []
        return await self.list_events(
            session,
            affinity_id=row.affinity_id,
            limit=limit,
        )

    async def list_events(
        self,
        session: AsyncSession,
        *,
        affinity_id: str,
        limit: int,
    ) -> list[AIRelationshipEvent]:
        """List recent persisted events for one affinity state."""

        result = await session.execute(
            select(AIRelationshipEventRecord)
            .where(AIRelationshipEventRecord.affinity_id == affinity_id)
            .order_by(
                AIRelationshipEventRecord.created_at.desc(),
                AIRelationshipEventRecord.id.desc(),
            )
            .limit(limit)
        )
        return [self._to_event(row) for row in result.scalars().all()]

    async def project_state(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> EmotionProjection:
        """Build the current emotion projection for one user within a scene."""

        row = await self._find_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is None:
            return project_emotion(
                self._build_default_state(
                    platform=platform,
                    group_id=group_id,
                    user_id=user_id,
                )
            )
        return project_emotion(self._build_effective_state(row))

    async def _find_row(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIAffinity | None:
        scope_key = build_affinity_scope_key(group_id)
        result = await session.execute(
            select(AIAffinity).where(
                AIAffinity.platform == platform,
                AIAffinity.scope_key == scope_key,
                AIAffinity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_create_row(
        self,
        session: AsyncSession,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIAffinity:
        row = await self._find_row(
            session,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is not None:
            return row

        scope_key = build_affinity_scope_key(group_id)
        row = AIAffinity(
            affinity_id=f"aff_{uuid4().hex}",
            platform=platform,
            group_id=group_id,
            scope_key=scope_key,
            user_id=user_id,
            score=0.0,
            mood_tags_json="[]",
            last_event_at=_utcnow_naive(),
            last_decay_at=None,
        )
        session.add(row)
        await session.flush()
        return row

    async def _persist_inactivity_decay(
        self,
        session: AsyncSession,
        row: AIAffinity,
    ) -> AIRelationshipState:
        state = self._to_state(row)
        decayed = self._build_effective_state(row)
        if (
            decayed.score == state.score
            and decayed.mood_tags == state.mood_tags
            and decayed.last_decay_at == state.last_decay_at
        ):
            return state

        row.score = decayed.score
        row.mood_tags_json = self._serialize_mood_tags(decayed.mood_tags)
        row.last_decay_at = (
            decayed.last_decay_at.replace(tzinfo=None)
            if decayed.last_decay_at is not None
            else None
        )
        await self._record_event(
            session,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type="absence_decay",
            score_delta=decayed.score - state.score,
            score_after=decayed.score,
            mood_tag=(decayed.mood_tags[-1] if decayed.mood_tags else None),
            reason="relationship drifted toward neutral after inactivity",
            created_at=row.last_decay_at or _utcnow_naive(),
        )
        await session.flush()
        return decayed

    async def _record_event(  # noqa: PLR0913
        self,
        session: AsyncSession,
        *,
        affinity_id: str,
        platform: str,
        group_id: str | None,
        user_id: str,
        event_type: AIRelationshipEventType,
        score_delta: float,
        score_after: float,
        mood_tag: str | None,
        reason: str | None,
        created_at: datetime,
    ) -> None:
        event = AIRelationshipEventRecord(
            event_id=f"rel_evt_{uuid4().hex}",
            affinity_id=affinity_id,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
            event_type=event_type,
            score_delta=score_delta,
            score_after=score_after,
            mood_tag=mood_tag,
            reason=reason,
            created_at=created_at,
        )
        session.add(event)

    @staticmethod
    def _serialize_mood_tags(mood_tags: tuple[str, ...]) -> str:
        return json.dumps(mood_tags, ensure_ascii=False)

    @staticmethod
    def _build_effective_state(row: AIAffinity) -> AIRelationshipState:
        state = AIRelationshipService._to_state(row)
        return apply_inactivity_decay(
            state,
            current_time=datetime.now(timezone.utc),
        )

    @staticmethod
    def _build_default_state(
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AIRelationshipState:
        scope_key = build_affinity_scope_key(group_id)
        identity = "|".join((platform, scope_key, user_id))
        return AIRelationshipState(
            affinity_id=(
                "aff_transient_"
                + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            ),
            platform=platform,
            group_id=group_id,
            user_id=user_id,
            score=0.0,
            mood_tags=(),
            last_event_at=None,
            last_decay_at=None,
        )

    @staticmethod
    def _to_state(row: AIAffinity) -> AIRelationshipState:
        mood_tags = tuple(json.loads(row.mood_tags_json or "[]"))
        last_event_at = None
        if row.last_event_at is not None:
            last_event_at = (
                row.last_event_at.replace(tzinfo=timezone.utc)
                if row.last_event_at.tzinfo is None
                else row.last_event_at
            )
        last_decay_at = None
        if row.last_decay_at is not None:
            last_decay_at = (
                row.last_decay_at.replace(tzinfo=timezone.utc)
                if row.last_decay_at.tzinfo is None
                else row.last_decay_at
            )
        return AIRelationshipState(
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            score=row.score,
            mood_tags=mood_tags,
            last_event_at=last_event_at,
            last_decay_at=last_decay_at,
        )

    @staticmethod
    def _to_event(row: AIRelationshipEventRecord) -> AIRelationshipEvent:
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        return AIRelationshipEvent(
            event_id=row.event_id,
            affinity_id=row.affinity_id,
            platform=row.platform,
            group_id=row.group_id,
            user_id=row.user_id,
            event_type=cast("AIRelationshipEventType", row.event_type),
            score_delta=row.score_delta,
            score_after=row.score_after,
            mood_tag=row.mood_tag,
            reason=row.reason,
            created_at=created_at,
        )


ai_relationship_service = AIRelationshipService()
