"""Future-task runtime scheduling service."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

from nonebot.log import logger

from apeiria.app.ai.future_task.models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
)
from apeiria.app.ai.future_task.repository import AIFutureTaskRepository

if TYPE_CHECKING:
    from apeiria.scheduler import SchedulerService

_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


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


@dataclass(frozen=True)
class AIFutureTaskRecoveryResult:
    """Result of recovering durable future-task scheduler jobs."""

    rescheduled_task_ids: tuple[str, ...] = ()
    failed_task_ids: tuple[str, ...] = ()


class AIFutureTaskService:
    """Domain service for durable AI future-task scheduling state."""

    def __init__(
        self,
        *,
        repository: AIFutureTaskRepository | None = None,
    ) -> None:
        self._repository = repository or AIFutureTaskRepository()

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
        self._repository.create_task(task)

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
        self._repository.save_task(task)

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

    async def recover_scheduled_tasks(
        self,
        *,
        now: datetime | None = None,
    ) -> AIFutureTaskRecoveryResult:
        """Recover scheduler jobs from durable task state."""

        current_time = _coerce_utc(now) if now is not None else _utcnow()
        rescheduled_task_ids: list[str] = []
        failed_task_ids: list[str] = []
        for task in self._repository.list_recoverable_tasks(now=current_time):
            if task.status == "pending":
                run_at = max(current_time, task.trigger_at)
                scheduler_job_id = self.schedule_task(task.task_id, run_at)
                if scheduler_job_id is None:
                    failed = replace(
                        task,
                        status="failed",
                        last_error="scheduler_recovery_failed",
                        completed_at=current_time,
                        recovery_reason="scheduler_recovery_failed",
                        updated_at=current_time,
                    )
                    self._repository.save_task(failed)
                    failed_task_ids.append(task.task_id)
                    continue
                self._repository.save_task(
                    replace(
                        task,
                        scheduler_job_id=scheduler_job_id,
                        updated_at=current_time,
                    )
                )
                rescheduled_task_ids.append(task.task_id)
                continue

            if task.status == "running":
                failed = replace(
                    task,
                    status="failed",
                    last_error="stale_running_recovered",
                    completed_at=current_time,
                    recovery_reason="stale_running_recovered",
                    updated_at=current_time,
                )
                self._repository.save_task(failed)
                failed_task_ids.append(task.task_id)

        return AIFutureTaskRecoveryResult(
            rescheduled_task_ids=tuple(rescheduled_task_ids),
            failed_task_ids=tuple(failed_task_ids),
        )

    async def list_tasks(
        self,
        *,
        limit: int,
        session_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        return self._repository.list_tasks(limit=limit, session_id=session_id)

    async def get_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        return self._repository.get_task(task_id=task_id)

    async def cancel_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        task = await self.get_task(task_id=task_id)
        if task is None:
            return None
        task = self._update_task_status(
            task_id=task_id,
            status="cancelled",
            last_error=None,
        )
        if task is None:
            return None
        if task.scheduler_job_id:
            try:
                _get_scheduler_service().remove_job(task.scheduler_job_id)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Future task job already absent: {}",
                    task.scheduler_job_id,
                )
        return task

    async def claim_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        return self._repository.claim_task(task_id=task_id, claimed_at=_utcnow())

    async def mark_task_running(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        return await self.claim_task(task_id=task_id)

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
        return self._repository.update_status(
            task_id=task_id,
            status=status,
            last_error=last_error,
            updated_at=_utcnow(),
        )


ai_future_task_service = AIFutureTaskService()

__all__ = [
    "AIFutureTaskCreateResult",
    "AIFutureTaskRecoveryResult",
    "AIFutureTaskService",
    "ai_future_task_service",
]
