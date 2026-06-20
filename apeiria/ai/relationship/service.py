from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session
from apeiria.db.models.ai_relationship import RelationshipScore

if TYPE_CHECKING:
    from apeiria.db.models.ai_settings import AIRuntimeSettings

_COLD_THRESHOLD = 20
_GUARDED_THRESHOLD = 40
_NEUTRAL_THRESHOLD = 60
_WARM_THRESHOLD = 80


async def get_score(
    user_id: str,
    session_id: str,
    *,
    settings: AIRuntimeSettings,
) -> RelationshipScore:
    async with get_session() as db:
        if not settings.relationship_isolate_by_session:
            row = (
                await db.execute(
                    select(RelationshipScore)
                    .where(RelationshipScore.user_id == user_id)
                    .order_by(RelationshipScore.last_updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        else:
            row = (
                await db.execute(
                    select(RelationshipScore).where(
                        RelationshipScore.user_id == user_id,
                        RelationshipScore.session_id == session_id,
                    )
                )
            ).scalar_one_or_none()

        if row is None:
            row = RelationshipScore(
                user_id=user_id,
                session_id=session_id,
                score=50,
                last_updated_at=_now_iso(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row

        now = datetime.now(timezone.utc)
        last_updated = datetime.fromisoformat(row.last_updated_at)
        age_days = (now - last_updated).total_seconds() / 86400
        half_life = settings.relationship_half_life_days
        effective = 50 + (row.score - 50) * (0.5 ** (age_days / half_life))
        row.score = effective
        row.last_updated_at = _now_iso()
        await db.commit()
        return row


async def adjust(
    user_id: str,
    session_id: str,
    delta: float,
) -> RelationshipScore:
    async with get_session() as db:
        row = (
            await db.execute(
                select(RelationshipScore).where(
                    RelationshipScore.user_id == user_id,
                    RelationshipScore.session_id == session_id,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            row = RelationshipScore(
                user_id=user_id,
                session_id=session_id,
                score=max(0.0, min(100.0, 50 + delta)),
                last_updated_at=_now_iso(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row

        row.score = max(0.0, min(100.0, row.score + delta))
        row.last_updated_at = _now_iso()
        await db.commit()
        return row


def project_emotion(score: float) -> str:
    if score < _COLD_THRESHOLD:
        return "冷淡"
    if score < _GUARDED_THRESHOLD:
        return "戒备"
    if score < _NEUTRAL_THRESHOLD:
        return "普通"
    if score < _WARM_THRESHOLD:
        return "亲近"
    return "亲密"
