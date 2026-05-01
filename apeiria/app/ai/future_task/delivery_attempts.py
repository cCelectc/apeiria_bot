"""Durable delivery-attempt state for proactive future-task replies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, cast
from uuid import uuid4

from apeiria.ai.diagnostics import sanitize_runtime_diagnostics
from apeiria.db.runtime import database_runtime

AIDeliveryAttemptStatus = Literal["pending", "delivered", "failed"]


class AIDeliveryAttemptRepositoryError(RuntimeError):
    """Raised when a delivery attempt write cannot be reloaded."""


@dataclass(frozen=True)
class AIDeliveryAttemptCreateInput:
    """Fields needed to create a durable proactive delivery attempt."""

    task_id: str
    trace_id: str
    session_id: str
    delivery_intent: str
    platform: str
    scene_type: str
    scene_id: str
    message_preview: str
    message_hash: str
    created_at: datetime


@dataclass(frozen=True)
class AIDeliveryAttemptRecord:
    """One durable proactive delivery attempt."""

    attempt_id: str
    task_id: str
    trace_id: str
    session_id: str
    delivery_intent: str
    platform: str
    scene_type: str
    scene_id: str
    message_preview: str
    message_hash: str
    status: AIDeliveryAttemptStatus
    reason: str | None
    diagnostics: dict[str, object]
    channel: str | None
    remote_message_id: str | None
    attempt_count: int
    delivered_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AIDeliveryAttemptRepository:
    """Own SQL operations for proactive delivery attempt idempotency."""

    def create_or_reuse_pending(
        self,
        create_input: AIDeliveryAttemptCreateInput,
    ) -> AIDeliveryAttemptRecord:
        with database_runtime.transaction_sync() as connection:
            row = connection.execute(
                _SELECT_ATTEMPT_FIELDS
                + """
                WHERE task_id = ? AND delivery_intent = ? AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (create_input.task_id, create_input.delivery_intent),
            ).fetchone()
            if row is not None:
                return row_to_attempt(row)

            attempt_id = f"delivery_attempt_{uuid4().hex}"
            timestamp = datetime_to_text(create_input.created_at)
            connection.execute(
                """
                INSERT INTO ai_delivery_attempt (
                    attempt_id,
                    task_id,
                    trace_id,
                    session_id,
                    delivery_intent,
                    platform,
                    scene_type,
                    scene_id,
                    message_preview,
                    message_hash,
                    status,
                    diagnostics_json,
                    attempt_count,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '{}', 0, ?, ?)
                """,
                (
                    attempt_id,
                    create_input.task_id,
                    create_input.trace_id,
                    create_input.session_id,
                    create_input.delivery_intent,
                    create_input.platform,
                    create_input.scene_type,
                    create_input.scene_id,
                    create_input.message_preview,
                    create_input.message_hash,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                _SELECT_ATTEMPT_FIELDS + " WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise AIDeliveryAttemptRepositoryError
        return row_to_attempt(row)

    def get_delivered_attempt(
        self,
        *,
        task_id: str,
        delivery_intent: str,
    ) -> AIDeliveryAttemptRecord | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_ATTEMPT_FIELDS
                + """
                WHERE task_id = ? AND delivery_intent = ? AND status = 'delivered'
                ORDER BY delivered_at DESC, id DESC
                LIMIT 1
                """,
                (task_id, delivery_intent),
            ).fetchone()
        return None if row is None else row_to_attempt(row)

    def mark_delivered(
        self,
        *,
        attempt_id: str,
        channel: str | None,
        remote_message_id: str | None,
        delivered_at: datetime,
    ) -> AIDeliveryAttemptRecord:
        timestamp = datetime_to_text(delivered_at)
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_delivery_attempt
                SET
                    status = 'delivered',
                    reason = NULL,
                    channel = ?,
                    remote_message_id = ?,
                    attempt_count = attempt_count + 1,
                    delivered_at = ?,
                    failed_at = NULL,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (channel, remote_message_id, timestamp, timestamp, attempt_id),
            )
            row = connection.execute(
                _SELECT_ATTEMPT_FIELDS + " WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return row_to_attempt(row)

    def mark_failed(
        self,
        *,
        attempt_id: str,
        reason: str | None,
        diagnostics: dict[str, Any] | None,
        failed_at: datetime,
    ) -> AIDeliveryAttemptRecord:
        timestamp = datetime_to_text(failed_at)
        diagnostics_json = json.dumps(
            sanitize_runtime_diagnostics(diagnostics),
            ensure_ascii=False,
            sort_keys=True,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_delivery_attempt
                SET
                    status = 'failed',
                    reason = ?,
                    diagnostics_json = ?,
                    attempt_count = attempt_count + 1,
                    delivered_at = NULL,
                    failed_at = ?,
                    updated_at = ?
                WHERE attempt_id = ?
                """,
                (reason, diagnostics_json, timestamp, timestamp, attempt_id),
            )
            row = connection.execute(
                _SELECT_ATTEMPT_FIELDS + " WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return row_to_attempt(row)


_SELECT_ATTEMPT_FIELDS = """
SELECT
    attempt_id,
    task_id,
    trace_id,
    session_id,
    delivery_intent,
    platform,
    scene_type,
    scene_id,
    message_preview,
    message_hash,
    status,
    reason,
    diagnostics_json,
    channel,
    remote_message_id,
    attempt_count,
    delivered_at,
    failed_at,
    created_at,
    updated_at
FROM ai_delivery_attempt
"""


def row_to_attempt(row: tuple[object, ...]) -> AIDeliveryAttemptRecord:
    return AIDeliveryAttemptRecord(
        attempt_id=str(row[0]),
        task_id=str(row[1]),
        trace_id=str(row[2]),
        session_id=str(row[3]),
        delivery_intent=str(row[4]),
        platform=str(row[5]),
        scene_type=str(row[6]),
        scene_id=str(row[7]),
        message_preview=str(row[8]),
        message_hash=str(row[9]),
        status=cast("AIDeliveryAttemptStatus", str(row[10])),
        reason=str(row[11]) if row[11] is not None else None,
        diagnostics=_load_json_dict(row[12]),
        channel=str(row[13]) if row[13] is not None else None,
        remote_message_id=str(row[14]) if row[14] is not None else None,
        attempt_count=int(str(row[15])),
        delivered_at=datetime_from_text(row[16]) if row[16] is not None else None,
        failed_at=datetime_from_text(row[17]) if row[17] is not None else None,
        created_at=datetime_from_text(row[18]),
        updated_at=datetime_from_text(row[19]),
    )


def datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_json_dict(value: object) -> dict[str, object]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


delivery_attempt_repository = AIDeliveryAttemptRepository()


__all__ = [
    "AIDeliveryAttemptCreateInput",
    "AIDeliveryAttemptRecord",
    "AIDeliveryAttemptRepository",
    "AIDeliveryAttemptRepositoryError",
    "AIDeliveryAttemptStatus",
    "delivery_attempt_repository",
]
