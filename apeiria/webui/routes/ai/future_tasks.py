"""AI future-task admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth
from apeiria.webui.routes.ai._auth_helpers import actor_username_from_claims

from .future_tasks_schemas import AIFutureTaskItem, to_ai_future_task_item

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


@router.get("/future-tasks", response_model=list[AIFutureTaskItem])
async def list_ai_future_tasks(
    _: Annotated[Any, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIFutureTaskItem]:
    tasks = await ai_application.future_tasks.list_tasks(limit=limit)
    return [to_ai_future_task_item(item) for item in tasks]


@router.delete("/future-tasks", response_model=AIFutureTaskItem | None)
async def cancel_ai_future_task(
    session: Annotated["AuthSession", Depends(require_auth)],
    task_id: Annotated[str, Query(min_length=1)],
) -> AIFutureTaskItem | None:
    task = await ai_application.future_tasks.cancel_task(
        task_id=task_id,
        actor_username=actor_username_from_claims(session),
    )
    if task is None:
        return None
    return to_ai_future_task_item(task)


__all__ = ["router"]
