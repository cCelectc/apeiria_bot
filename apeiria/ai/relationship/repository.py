"""Async SQLAlchemy persistence for AI relationship state and events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_relationship import AIAffinity, AIRelationshipEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.ai.relationship.models import AIRelationshipEventType


@dataclass
class AffinityRow:
    affinity_id: str
    platform: str
    user_id: str
    score: int
    mood_tags_json: str
    last_event_at: datetime
    last_decay_at: datetime | None


@dataclass(frozen=True)
class RelationshipEventRow:
    event_id: str
    affinity_id: str
    platform: str
    user_id: str
    scene_id: str | None
    event_type: str
    score_delta: int
    score_after: int
    mood_tag: str | None
    reason: str | None
    created_at: datetime


class RelationshipRepository:
    """Own low-level SQL operations for relationship persistence."""

    async def find_row(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> AffinityRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIAffinity).where(
                    AIAffinity.platform == platform,
                    AIAffinity.user_id == user_id,
                )
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _orm_to_affinity_row(item)

    async def get_or_create_row(
        self,
        session: "AsyncSession",
        *,
        platform: str,
        user_id: str,
    ) -> AffinityRow:
        result = await session.execute(
            select(AIAffinity).where(
                AIAffinity.platform == platform,
                AIAffinity.user_id == user_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is not None:
            return _orm_to_affinity_row(item)

        now = _epoch_ms()
        stmt = insert(AIAffinity).values(
            affinity_id=f"aff_{uuid4().hex}",
            platform=platform,
            user_id=user_id,
            score=0,
            mood_tags_json="[]",
            last_event_at=now,
            last_decay_at=None,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[AIAffinity.platform, AIAffinity.user_id],
        )
        await session.execute(stmt)
        await session.flush()
        result = await session.execute(
            select(AIAffinity).where(
                AIAffinity.platform == platform,
                AIAffinity.user_id == user_id,
            )
        )
        item = result.scalar_one()
        return _orm_to_affinity_row(item)

    async def list_rows(
        self,
        *,
        limit: int,
    ) -> list[AffinityRow]:
        async with get_session() as session:
            result = await session.execute(
                select(AIAffinity)
                .order_by(
                    AIAffinity.last_event_at.desc(), AIAffinity.affinity_id.desc()
                )
                .limit(limit)
            )
            items = result.scalars().all()
        return [_orm_to_affinity_row(item) for item in items]

    async def list_event_rows(
        self,
        *,
        affinity_id: str,
        limit: int,
    ) -> list[RelationshipEventRow]:
        async with get_session() as session:
            result = await session.execute(
                select(AIRelationshipEvent)
                .where(AIRelationshipEvent.affinity_id == affinity_id)
                .order_by(
                    AIRelationshipEvent.created_at.desc(),
                    AIRelationshipEvent.event_id.desc(),
                )
                .limit(limit)
            )
            items = result.scalars().all()
        return [_orm_to_event_row(item) for item in items]

    async def list_event_rows_since(
        self,
        *,
        affinity_id: str,
        since: datetime,
        limit: int,
    ) -> list[RelationshipEventRow]:
        since_ms = int(since.timestamp() * 1000)
        async with get_session() as session:
            result = await session.execute(
                select(AIRelationshipEvent)
                .where(
                    AIRelationshipEvent.affinity_id == affinity_id,
                    AIRelationshipEvent.created_at >= since_ms,
                )
                .order_by(
                    AIRelationshipEvent.created_at.desc(),
                    AIRelationshipEvent.event_id.desc(),
                )
                .limit(limit)
            )
            items = result.scalars().all()
        return [_orm_to_event_row(item) for item in items]

    async def update_row(self, session: "AsyncSession", row: AffinityRow) -> None:
        await session.execute(
            update(AIAffinity)
            .where(AIAffinity.affinity_id == row.affinity_id)
            .values(
                score=row.score,
                mood_tags_json=row.mood_tags_json,
                last_event_at=_datetime_to_epoch_ms(row.last_event_at),
                last_decay_at=_optional_datetime_to_epoch_ms(row.last_decay_at),
            )
        )

    async def record_event(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        affinity_id: str,
        platform: str,
        user_id: str,
        scene_id: str | None,
        event_type: "AIRelationshipEventType",
        score_delta: int,
        score_after: int,
        mood_tag: str | None,
        reason: str | None,
        created_at: datetime,
    ) -> None:
        event = AIRelationshipEvent(
            event_id=f"rel_evt_{uuid4().hex}",
            affinity_id=affinity_id,
            platform=platform,
            user_id=user_id,
            scene_id=scene_id,
            event_type=event_type,
            score_delta=score_delta,
            score_after=score_after,
            mood_tag=mood_tag,
            reason=reason,
            created_at=_datetime_to_epoch_ms(created_at),
        )
        session.add(event)


def serialize_mood_tags(mood_tags: tuple[str, ...]) -> str:
    return json.dumps(mood_tags, ensure_ascii=False)


def deserialize_mood_tags(raw_json: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _orm_to_affinity_row(item: AIAffinity) -> AffinityRow:
    return AffinityRow(
        affinity_id=item.affinity_id,
        platform=item.platform,
        user_id=item.user_id,
        score=item.score,
        mood_tags_json=item.mood_tags_json or "[]",
        last_event_at=_epoch_ms_to_datetime(item.last_event_at),
        last_decay_at=_epoch_ms_to_datetime(item.last_decay_at)
        if item.last_decay_at is not None
        else None,
    )


def _orm_to_event_row(item: AIRelationshipEvent) -> RelationshipEventRow:
    return RelationshipEventRow(
        event_id=item.event_id,
        affinity_id=item.affinity_id,
        platform=item.platform,
        user_id=item.user_id,
        scene_id=item.scene_id,
        event_type=item.event_type,
        score_delta=item.score_delta,
        score_after=item.score_after,
        mood_tag=item.mood_tag,
        reason=item.reason,
        created_at=_epoch_ms_to_datetime(item.created_at),
    )


def _epoch_ms_to_datetime(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def _datetime_to_epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _optional_datetime_to_epoch_ms(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return _datetime_to_epoch_ms(dt)
