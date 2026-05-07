"""Schema models for AI future-task routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition


class AIFutureTaskItem(BaseModel):
    task_id: str
    session_id: str
    platform: str
    scene_type: str
    scene_id: str
    user_id: str | None = None
    title: str
    description: str
    trigger_at: str
    status: str
    source_message_id: str | None = None
    scheduler_job_id: str | None = None
    last_error: str | None = None
    created_at: str
    updated_at: str


def to_ai_future_task_item(item: "AIFutureTaskDefinition") -> AIFutureTaskItem:
    return AIFutureTaskItem(
        task_id=item.task_id,
        session_id=item.session_id,
        platform=item.platform,
        scene_type=item.scene_type,
        scene_id=item.scene_id,
        user_id=item.user_id,
        title=item.title,
        description=item.description,
        trigger_at=item.trigger_at.isoformat(),
        status=item.status,
        source_message_id=item.source_message_id,
        scheduler_job_id=item.scheduler_job_id,
        last_error=item.last_error,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
