"""Async SQLAlchemy repository for durable AI future-task state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from sqlalchemy import select, update

from apeiria.app.ai.future_tasks.models import (
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
)
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_tasks import AIFutureTask

if TYPE_CHECKING:
    from apeiria.conversation.models import SceneType


class AIFutureTaskRepository:
    """Own durable future-task SQL operations."""

    async def create_task(self, task: AIFutureTaskDefinition) -> AIFutureTaskDefinition:
        async with get_session() as session:
            now = _epoch_ms()
            item = AIFutureTask(
                task_id=task.task_id,
                session_id=task.session_id,
                platform=task.platform,
                scene_type=task.scene_type,
                scene_id=task.scene_id,
                user_id=task.user_id,
                title=task.title,
                description=task.description,
                trigger_at=_datetime_to_epoch_ms(task.trigger_at),
                status=task.status,
                source_message_id=task.source_message_id,
                scheduler_job_id=task.scheduler_job_id,
                last_error=task.last_error,
                claim_count=task.claim_count,
                claimed_at=_optional_datetime_to_epoch_ms(task.claimed_at),
                completed_at=_optional_datetime_to_epoch_ms(task.completed_at),
                recovery_reason=task.recovery_reason,
                created_at=_datetime_to_epoch_ms(task.created_at),
                updated_at=now,
            )
            session.add(item)
            await session.commit()
        return task

    async def save_task(self, task: AIFutureTaskDefinition) -> AIFutureTaskDefinition:
        now = _epoch_ms()
        async with get_session() as session:
            await session.execute(
                update(AIFutureTask)
                .where(AIFutureTask.task_id == task.task_id)
                .values(
                    session_id=task.session_id,
                    platform=task.platform,
                    scene_type=task.scene_type,
                    scene_id=task.scene_id,
                    user_id=task.user_id,
                    title=task.title,
                    description=task.description,
                    trigger_at=_datetime_to_epoch_ms(task.trigger_at),
                    status=task.status,
                    source_message_id=task.source_message_id,
                    scheduler_job_id=task.scheduler_job_id,
                    last_error=task.last_error,
                    claim_count=task.claim_count,
                    claimed_at=_optional_datetime_to_epoch_ms(task.claimed_at),
                    completed_at=_optional_datetime_to_epoch_ms(task.completed_at),
                    recovery_reason=task.recovery_reason,
                    created_at=_datetime_to_epoch_ms(task.created_at),
                    updated_at=now,
                )
            )
            await session.commit()
        return task

    async def get_task(self, *, task_id: str) -> AIFutureTaskDefinition | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIFutureTask).where(AIFutureTask.task_id == task_id)
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _orm_to_task(item)

    async def list_tasks(
        self,
        *,
        limit: int,
        session_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        stmt = select(AIFutureTask)
        if session_id is not None:
            stmt = stmt.where(AIFutureTask.session_id == session_id)
        stmt = stmt.order_by(
            AIFutureTask.created_at.desc(), AIFutureTask.task_id.desc()
        ).limit(limit)
        async with get_session() as session:
            result = await session.execute(stmt)
            items = result.scalars().all()
        return [_orm_to_task(item) for item in items]

    async def claim_task(
        self,
        *,
        task_id: str,
        claimed_at: datetime,
    ) -> AIFutureTaskDefinition | None:
        claimed_ms = _datetime_to_epoch_ms(claimed_at)
        async with get_session() as session:
            result = await session.execute(
                update(AIFutureTask)
                .where(
                    AIFutureTask.task_id == task_id,
                    AIFutureTask.status == "pending",
                )
                .values(
                    status="running",
                    last_error=None,
                    claim_count=AIFutureTask.claim_count + 1,
                    claimed_at=claimed_ms,
                    updated_at=claimed_ms,
                )
            )
            if (rowcount(result) or 0) != 1:
                return None
            await session.commit()
            row = await session.execute(
                select(AIFutureTask).where(AIFutureTask.task_id == task_id)
            )
            item = row.scalar_one_or_none()
        if item is None:
            return None
        return _orm_to_task(item)

    async def update_status(
        self,
        *,
        task_id: str,
        status: AIFutureTaskStatus,
        last_error: str | None,
        updated_at: datetime,
    ) -> AIFutureTaskDefinition | None:
        current = await self.get_task(task_id=task_id)
        if current is None:
            return None
        completed_at = updated_at if status in {"sent", "cancelled", "failed"} else None
        next_task = replace(
            current,
            status=status,
            last_error=last_error,
            completed_at=completed_at,
            updated_at=updated_at,
        )
        return await self.save_task(next_task)

    async def list_recoverable_tasks(
        self,
        *,
        now: datetime,
    ) -> list[AIFutureTaskDefinition]:
        del now
        async with get_session() as session:
            result = await session.execute(
                select(AIFutureTask)
                .where(AIFutureTask.status.in_(("pending", "running")))
                .order_by(AIFutureTask.trigger_at.asc(), AIFutureTask.task_id.asc())
            )
            items = result.scalars().all()
        return [_orm_to_task(item) for item in items]


def _orm_to_task(item: AIFutureTask) -> AIFutureTaskDefinition:
    return AIFutureTaskDefinition(
        task_id=item.task_id,
        session_id=item.session_id,
        platform=item.platform,
        scene_type=cast("SceneType", item.scene_type),
        scene_id=item.scene_id,
        user_id=item.user_id,
        title=item.title,
        description=item.description,
        trigger_at=_epoch_ms_to_datetime(item.trigger_at),
        status=cast("AIFutureTaskStatus", item.status),
        source_message_id=item.source_message_id,
        scheduler_job_id=item.scheduler_job_id,
        last_error=item.last_error,
        claim_count=item.claim_count,
        claimed_at=_epoch_ms_to_datetime(item.claimed_at)
        if item.claimed_at is not None
        else None,
        completed_at=_epoch_ms_to_datetime(item.completed_at)
        if item.completed_at is not None
        else None,
        recovery_reason=item.recovery_reason,
        created_at=_epoch_ms_to_datetime(item.created_at),
        updated_at=_epoch_ms_to_datetime(item.updated_at),
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


__all__ = ["AIFutureTaskRepository"]
