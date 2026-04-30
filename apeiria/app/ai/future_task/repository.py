"""SQLite repository for durable AI future-task state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from apeiria.app.ai.future_task.models import (
    AIFutureTaskDefinition,
    AIFutureTaskStatus,
)
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.conversation.models import SceneType


class AIFutureTaskRepository:
    """Own durable future-task SQL operations."""

    def create_task(self, task: AIFutureTaskDefinition) -> AIFutureTaskDefinition:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_future_task (
                    task_id,
                    session_id,
                    platform,
                    scene_type,
                    scene_id,
                    user_id,
                    title,
                    description,
                    trigger_at,
                    status,
                    source_message_id,
                    scheduler_job_id,
                    last_error,
                    claim_count,
                    claimed_at,
                    completed_at,
                    recovery_reason,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _task_values(task),
            )
        return task

    def save_task(self, task: AIFutureTaskDefinition) -> AIFutureTaskDefinition:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_future_task
                SET
                    session_id = ?,
                    platform = ?,
                    scene_type = ?,
                    scene_id = ?,
                    user_id = ?,
                    title = ?,
                    description = ?,
                    trigger_at = ?,
                    status = ?,
                    source_message_id = ?,
                    scheduler_job_id = ?,
                    last_error = ?,
                    claim_count = ?,
                    claimed_at = ?,
                    completed_at = ?,
                    recovery_reason = ?,
                    created_at = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    task.session_id,
                    task.platform,
                    task.scene_type,
                    task.scene_id,
                    task.user_id,
                    task.title,
                    task.description,
                    datetime_to_text(task.trigger_at),
                    task.status,
                    task.source_message_id,
                    task.scheduler_job_id,
                    task.last_error,
                    task.claim_count,
                    datetime_to_text(task.claimed_at),
                    datetime_to_text(task.completed_at),
                    task.recovery_reason,
                    datetime_to_text(task.created_at),
                    datetime_to_text(task.updated_at),
                    task.task_id,
                ),
            )
        return task

    def get_task(self, *, task_id: str) -> AIFutureTaskDefinition | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_TASK_FIELDS + " WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return None if row is None else row_to_task(row)

    def list_tasks(
        self,
        *,
        limit: int,
        session_id: str | None = None,
    ) -> list[AIFutureTaskDefinition]:
        if session_id is None:
            query = _SELECT_TASK_FIELDS + " ORDER BY created_at DESC, id DESC LIMIT ?"
            params: tuple[object, ...] = (limit,)
        else:
            query = (
                _SELECT_TASK_FIELDS
                + """
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """
            )
            params = (session_id, limit)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(query, params).fetchall()
        return [row_to_task(row) for row in rows]

    def claim_task(
        self,
        *,
        task_id: str,
        claimed_at: datetime,
    ) -> AIFutureTaskDefinition | None:
        timestamp = datetime_to_text(claimed_at)
        with database_runtime.transaction_sync() as connection:
            cursor = connection.execute(
                """
                UPDATE ai_future_task
                SET
                    status = 'running',
                    last_error = NULL,
                    claim_count = claim_count + 1,
                    claimed_at = ?,
                    updated_at = ?
                WHERE task_id = ? AND status = 'pending'
                """,
                (timestamp, timestamp, task_id),
            )
            if int(cursor.rowcount or 0) != 1:
                return None
            row = connection.execute(
                _SELECT_TASK_FIELDS + " WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return None if row is None else row_to_task(row)

    def update_status(
        self,
        *,
        task_id: str,
        status: AIFutureTaskStatus,
        last_error: str | None,
        updated_at: datetime,
    ) -> AIFutureTaskDefinition | None:
        current = self.get_task(task_id=task_id)
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
        return self.save_task(next_task)

    def list_recoverable_tasks(
        self,
        *,
        now: datetime,
    ) -> list[AIFutureTaskDefinition]:
        del now
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_TASK_FIELDS
                + """
                WHERE status IN ('pending', 'running')
                ORDER BY trigger_at ASC, id ASC
                """
            ).fetchall()
        return [row_to_task(row) for row in rows]


_SELECT_TASK_FIELDS = """
SELECT
    id,
    task_id,
    session_id,
    platform,
    scene_type,
    scene_id,
    user_id,
    title,
    description,
    trigger_at,
    status,
    source_message_id,
    scheduler_job_id,
    last_error,
    claim_count,
    claimed_at,
    completed_at,
    recovery_reason,
    created_at,
    updated_at
FROM ai_future_task
"""


def _task_values(task: AIFutureTaskDefinition) -> tuple[object, ...]:
    return (
        task.task_id,
        task.session_id,
        task.platform,
        task.scene_type,
        task.scene_id,
        task.user_id,
        task.title,
        task.description,
        datetime_to_text(task.trigger_at),
        task.status,
        task.source_message_id,
        task.scheduler_job_id,
        task.last_error,
        task.claim_count,
        datetime_to_text(task.claimed_at),
        datetime_to_text(task.completed_at),
        task.recovery_reason,
        datetime_to_text(task.created_at),
        datetime_to_text(task.updated_at),
    )


def row_to_task(row: tuple[object, ...]) -> AIFutureTaskDefinition:
    return AIFutureTaskDefinition(
        task_id=str(row[1]),
        session_id=str(row[2]),
        platform=str(row[3]),
        scene_type=cast("SceneType", str(row[4])),
        scene_id=str(row[5]),
        user_id=str(row[6]) if row[6] is not None else None,
        title=str(row[7]),
        description=str(row[8]),
        trigger_at=datetime_from_text(row[9]),
        status=cast("AIFutureTaskStatus", str(row[10])),
        source_message_id=str(row[11]) if row[11] is not None else None,
        scheduler_job_id=str(row[12]) if row[12] is not None else None,
        last_error=str(row[13]) if row[13] is not None else None,
        claim_count=int(str(row[14])),
        claimed_at=datetime_from_text(row[15]) if row[15] is not None else None,
        completed_at=datetime_from_text(row[16]) if row[16] is not None else None,
        recovery_reason=str(row[17]) if row[17] is not None else None,
        created_at=datetime_from_text(row[18]),
        updated_at=datetime_from_text(row[19]),
    )


def datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = ["AIFutureTaskRepository"]
