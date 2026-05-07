"""AI future-tasks application entry and durable task exports."""

from __future__ import annotations

from dataclasses import dataclass, field

from .execution import execute_future_task
from .models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
    AIFutureTaskToolAction,
    AIFutureTaskToolInput,
    AIFutureTaskToolItem,
    AIFutureTaskToolOutput,
)
from .service import (
    AIFutureTaskCreateResult,
    AIFutureTaskRecoveryResult,
    AIFutureTaskService,
    ai_future_task_service,
)


@dataclass(frozen=True, slots=True)
class AIFutureTasksEntry:
    """Application entry for durable AI future-task behavior."""

    service: AIFutureTaskService = field(default_factory=lambda: ai_future_task_service)

    async def create_task(
        self,
        create_input: AIFutureTaskCreateInput,
    ) -> AIFutureTaskCreateResult:
        """Create and schedule one durable future task."""

        return await self.service.create_task(create_input)

    async def recover_scheduled_tasks(
        self,
    ) -> AIFutureTaskRecoveryResult:
        """Recover scheduler jobs from durable task state."""

        return await self.service.recover_scheduled_tasks()

    async def list_tasks(
        self,
        *,
        limit: int,
        session_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        """List durable future tasks."""

        return await self.service.list_tasks(limit=limit, session_id=session_id)

    async def get_task(
        self,
        *,
        task_id: str,
    ) -> AIFutureTaskDefinition | None:
        """Load one durable future task."""

        return await self.service.get_task(task_id=task_id)

    async def cancel_task(
        self,
        *,
        task_id: str,
        actor_username: str | None = None,
    ) -> AIFutureTaskDefinition | None:
        """Cancel one durable future task."""

        del actor_username
        return await self.service.cancel_task(task_id=task_id)


__all__ = [
    "AIFutureTaskCreateInput",
    "AIFutureTaskCreateResult",
    "AIFutureTaskDefinition",
    "AIFutureTaskRecoveryResult",
    "AIFutureTaskService",
    "AIFutureTaskStatus",
    "AIFutureTaskToolAction",
    "AIFutureTaskToolInput",
    "AIFutureTaskToolItem",
    "AIFutureTaskToolOutput",
    "AIFutureTasksEntry",
    "ai_future_task_service",
    "execute_future_task",
]
