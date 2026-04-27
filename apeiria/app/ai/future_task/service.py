"""Future-task runtime scheduling service."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

from nonebot.log import logger

from apeiria.app.ai.future_task.models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
)

if TYPE_CHECKING:
    from apeiria.scheduler import SchedulerService

_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_scheduler_service() -> "SchedulerService":
    from apeiria.scheduler import scheduler_service

    return scheduler_service


@dataclass(frozen=True)
class AIFutureTaskCreateResult:
    """Result of creating and scheduling one future task."""

    task: AIFutureTaskDefinition
    scheduler_job_id: str | None


class AIFutureTaskService:
    """In-memory scheduling state for AI future tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, AIFutureTaskDefinition] = {}
        self._lock = RLock()

    async def create_task(
        self,
        create_input: AIFutureTaskCreateInput,
    ) -> AIFutureTaskCreateResult:
        task_id = f"future_task_{uuid4().hex}"
        now = _utcnow()
        task = AIFutureTaskDefinition(
            task_id=task_id,
            session_id=create_input.session_id,
            platform=create_input.platform,
            scene_type=create_input.scene_type,
            scene_id=create_input.scene_id,
            user_id=create_input.user_id,
            title=create_input.title,
            description=create_input.description,
            trigger_at=_coerce_utc(create_input.trigger_at),
            status="pending",
            source_message_id=create_input.source_message_id,
            scheduler_job_id=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task_id] = task

        scheduler_job_id = self.schedule_task(task_id, task.trigger_at)
        if scheduler_job_id is None:
            task = replace(
                task,
                status="failed",
                last_error="Failed to schedule future task",
                updated_at=_utcnow(),
            )
        else:
            task = replace(
                task,
                scheduler_job_id=scheduler_job_id,
                updated_at=_utcnow(),
            )
        with self._lock:
            self._tasks[task_id] = task

        return AIFutureTaskCreateResult(
            task=task,
            scheduler_job_id=scheduler_job_id,
        )

    def schedule_task(self, task_id: str, trigger_at: datetime) -> str | None:
        from apeiria.app.ai.future_task.execution import execute_future_task

        try:
            return _get_scheduler_service().add_job(
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
        *,
        limit: int,
        session_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        with self._lock:
            tasks = list(self._tasks.values())
        if session_id is not None:
            tasks = [task for task in tasks if task.session_id == session_id]
        tasks.sort(key=lambda item: item.created_at, reverse=True)
        return tasks[:limit]

    async def get_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        with self._lock:
            return self._tasks.get(task_id)

    async def cancel_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        task = await self.get_task(task_id=task_id)
        if task is None:
            return None
        task = replace(task, status="cancelled", updated_at=_utcnow())
        if task.scheduler_job_id:
            try:
                _get_scheduler_service().remove_job(task.scheduler_job_id)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Future task job already absent: {}",
                    task.scheduler_job_id,
                )
        with self._lock:
            self._tasks[task_id] = task
        return task

    async def mark_task_running(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        return self._update_task_status(
            task_id=task_id,
            status="running",
            last_error=None,
        )

    async def mark_task_sent(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        return self._update_task_status(
            task_id=task_id,
            status="sent",
            last_error=None,
        )

    async def mark_task_failed(
        self,
        *,
        task_id: str,
        error: str,
    ) -> AIFutureTaskDefinition | None:
        return self._update_task_status(
            task_id=task_id,
            status="failed",
            last_error=error,
        )

    @staticmethod
    def build_confirmation_message(task: AIFutureTaskDefinition) -> str:
        trigger_at = task.trigger_at.astimezone(_DISPLAY_TIMEZONE)
        return f"好的，我会在 {trigger_at:%Y-%m-%d %H:%M} 提醒你：{task.description}"

    @staticmethod
    def build_schedule_failed_message(task: AIFutureTaskDefinition) -> str:
        return f"我记下了这个提醒，但这次没有成功安排任务：{task.description}"

    def _update_task_status(
        self,
        *,
        task_id: str,
        status: AIFutureTaskStatus,
        last_error: str | None,
    ) -> AIFutureTaskDefinition | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task = replace(
                task,
                status=status,
                last_error=last_error,
                updated_at=_utcnow(),
            )
            self._tasks[task_id] = task
            return task


ai_future_task_service = AIFutureTaskService()

__all__ = [
    "AIFutureTaskCreateResult",
    "AIFutureTaskService",
    "ai_future_task_service",
]
