"""Future-task persistence and scheduling service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from nonebot.log import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from apeiria.app.ai.future_task.models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
)
from apeiria.infra.db.models import AIFutureTask
from apeiria.infra.scheduler.service import scheduler_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ScopeType

_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class AIFutureTaskCreateResult:
    """Result of creating and scheduling one future task."""

    task: AIFutureTaskDefinition
    scheduler_job_id: str | None


class AIFutureTaskService:
    """Persistence and minimal scheduling for AI future tasks."""

    async def create_task(
        self,
        session: "AsyncSession",
        create_input: AIFutureTaskCreateInput,
    ) -> AIFutureTaskCreateResult:
        task_id = f"future_task_{uuid4().hex}"
        row = AIFutureTask(
            task_id=task_id,
            conversation_id=create_input.conversation_id,
            platform=create_input.platform,
            scope_type=create_input.scope_type,
            scope_id=create_input.scope_id,
            user_id=create_input.user_id,
            title=create_input.title,
            description=create_input.description,
            trigger_at=create_input.trigger_at.astimezone(timezone.utc).replace(
                tzinfo=None
            ),
            status="pending",
            source_turn_id=create_input.source_turn_id,
        )
        session.add(row)
        await session.flush()

        scheduler_job_id = self.schedule_task(task_id, create_input.trigger_at)
        if scheduler_job_id is None:
            row.status = "failed"
            row.last_error = "Failed to schedule future task"
            row.updated_at = _utcnow_naive()
        else:
            row.scheduler_job_id = scheduler_job_id
        await session.flush()

        return AIFutureTaskCreateResult(
            task=self._to_definition(row),
            scheduler_job_id=scheduler_job_id,
        )

    def schedule_task(self, task_id: str, trigger_at: datetime) -> str | None:
        try:
            return scheduler_service.add_job(
                execute_future_task,
                "date",
                run_date=trigger_at,
                id=task_id,
                name=f"AI Future Task {task_id}",
                args=[task_id],
                replace_existing=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "Failed to schedule AI future task {}",
                task_id,
            )
            return None

    async def list_tasks(
        self,
        session: "AsyncSession",
        *,
        limit: int,
        conversation_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        query = select(AIFutureTask)
        if conversation_id is not None:
            query = query.where(AIFutureTask.conversation_id == conversation_id)
        query = query.order_by(AIFutureTask.created_at.desc(), AIFutureTask.id.desc())
        result = await session.execute(query.limit(limit))
        return [self._to_definition(row) for row in result.scalars().all()]

    async def get_task(
        self,
        session: "AsyncSession",
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        result = await session.execute(
            select(AIFutureTask).where(AIFutureTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_definition(row)

    async def cancel_task(
        self,
        session: "AsyncSession",
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        result = await session.execute(
            select(AIFutureTask).where(AIFutureTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "cancelled"
        row.updated_at = _utcnow_naive()
        if row.scheduler_job_id:
            try:
                scheduler_service.remove_job(row.scheduler_job_id)
            except Exception:  # noqa: BLE001
                logger.debug("Future task job already absent: {}", row.scheduler_job_id)
        await session.flush()
        return self._to_definition(row)

    async def mark_task_running(
        self,
        session: "AsyncSession",
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        result = await session.execute(
            select(AIFutureTask).where(AIFutureTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "running"
        row.last_error = None
        row.updated_at = _utcnow_naive()
        await session.flush()
        return self._to_definition(row)

    async def mark_task_sent(
        self,
        session: "AsyncSession",
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        result = await session.execute(
            select(AIFutureTask).where(AIFutureTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "sent"
        row.last_error = None
        row.updated_at = _utcnow_naive()
        await session.flush()
        return self._to_definition(row)

    async def mark_task_failed(
        self,
        session: "AsyncSession",
        *,
        task_id: str,
        error: str,
    ) -> AIFutureTaskDefinition | None:
        result = await session.execute(
            select(AIFutureTask).where(AIFutureTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "failed"
        row.last_error = error
        row.updated_at = _utcnow_naive()
        await session.flush()
        return self._to_definition(row)

    @staticmethod
    def build_confirmation_message(task: AIFutureTaskDefinition) -> str:
        trigger_at = task.trigger_at.astimezone(_DISPLAY_TIMEZONE)
        return f"好的，我会在 {trigger_at:%Y-%m-%d %H:%M} 提醒你：{task.description}"

    @staticmethod
    def build_schedule_failed_message(task: AIFutureTaskDefinition) -> str:
        return f"我记下了这个提醒，但这次没有成功安排任务：{task.description}"

    @staticmethod
    def _to_definition(row: AIFutureTask) -> AIFutureTaskDefinition:
        trigger_at = (
            row.trigger_at.replace(tzinfo=timezone.utc)
            if row.trigger_at.tzinfo is None
            else row.trigger_at
        )
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        updated_at = (
            row.updated_at.replace(tzinfo=timezone.utc)
            if row.updated_at.tzinfo is None
            else row.updated_at
        )
        return AIFutureTaskDefinition(
            task_id=row.task_id,
            conversation_id=row.conversation_id,
            platform=row.platform,
            scope_type=cast("ScopeType", row.scope_type),
            scope_id=row.scope_id,
            user_id=row.user_id,
            title=row.title,
            description=row.description,
            trigger_at=trigger_at,
            status=cast("AIFutureTaskStatus", row.status),
            source_turn_id=row.source_turn_id,
            scheduler_job_id=row.scheduler_job_id,
            last_error=row.last_error,
            created_at=created_at,
            updated_at=updated_at,
        )


async def execute_future_task(task_id: str) -> None:
    """Wake the AI runtime for one due future task."""

    async with get_session() as session:
        task = await ai_future_task_service.get_task(session, task_id=task_id)
        if task is None or task.status != "pending":
            return
        await ai_future_task_service.mark_task_running(session, task_id=task_id)
        await session.commit()

    try:
        from apeiria.app.ai.runtime.service import ai_runtime_service

        runtime_result = await ai_runtime_service.handle_future_task(task_id)
    except Exception as exc:  # noqa: BLE001
        async with get_session() as session:
            await ai_future_task_service.mark_task_failed(
                session,
                task_id=task_id,
                error=str(exc),
            )
            await session.commit()
        logger.opt(exception=exc).warning(
            "Failed to execute AI future task {}",
            task_id,
        )
        return

    async with get_session() as session:
        task = await ai_future_task_service.get_task(session, task_id=task_id)
        if task is None or task.status != "running":
            return
        if runtime_result is None:
            await ai_future_task_service.mark_task_failed(
                session,
                task_id=task_id,
                error="future task runtime produced no reply",
            )
        elif (
            runtime_result.delivery_result is None
            or not runtime_result.delivery_result.delivered
        ):
            await ai_future_task_service.mark_task_failed(
                session,
                task_id=task_id,
                error=(
                    runtime_result.delivery_result.error
                    if runtime_result.delivery_result is not None
                    and runtime_result.delivery_result.error
                    else "future task delivery failed"
                ),
            )
        else:
            await ai_future_task_service.mark_task_sent(session, task_id=task_id)
        await session.commit()


ai_future_task_service = AIFutureTaskService()

__all__ = [
    "AIFutureTaskCreateResult",
    "AIFutureTaskService",
    "ai_future_task_service",
    "execute_future_task",
]
