"""AI future-task admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.admin.service import ai_admin_service
from apeiria.ai.webui.schemas import AIFutureTaskItem
from apeiria.ai.webui.support import to_ai_future_task_item
from apeiria.webui.auth import require_control_panel

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/future-tasks", response_model=list[AIFutureTaskItem])
async def list_ai_future_tasks(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIFutureTaskItem]:
    tasks = await ai_admin_service.list_future_tasks(limit=limit)
    return [to_ai_future_task_item(item) for item in tasks]


@router.delete("/future-tasks", response_model=AIFutureTaskItem | None)
async def cancel_ai_future_task(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    task_id: Annotated[str, Query(min_length=1)],
) -> AIFutureTaskItem | None:
    task = await ai_admin_service.cancel_future_task(
        task_id=task_id,
        actor_username=_actor_username_from_claims(session),
    )
    if task is None:
        return None
    return to_ai_future_task_item(task)


__all__ = ["router"]
