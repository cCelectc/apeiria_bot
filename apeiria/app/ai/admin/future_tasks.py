"""Future-task admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.future_task import ai_future_task_service

if TYPE_CHECKING:
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition


class FutureTasksAdminMixin:
    """Admin CRUD for AI future tasks."""

    async def list_future_tasks(
        self,
        *,
        limit: int = 20,
    ) -> list["AIFutureTaskDefinition"]:
        return await ai_future_task_service.list_tasks(limit=limit)

    async def cancel_future_task(
        self,
        *,
        task_id: str,
        actor_username: str | None = None,
    ) -> "AIFutureTaskDefinition | None":
        task = await ai_future_task_service.cancel_task(task_id=task_id)
        if task is not None:
            record_ai_admin_audit(
                "ai_future_task_cancelled",
                actor_username=actor_username,
                detail=f"{task.task_id} {task.title}",
            )
            return task
        return None


__all__ = ["FutureTasksAdminMixin"]
