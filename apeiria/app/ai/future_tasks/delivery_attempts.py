"""Async SQLAlchemy persistence for proactive future-task delivery attempts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy import select, update

from apeiria.ai.diagnostics import sanitize_runtime_diagnostics
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.ai_tasks import AIDeliveryAttempt

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

    async def create_or_reuse_pending(
        self,
        create_input: AIDeliveryAttemptCreateInput,
    ) -> AIDeliveryAttemptRecord:
        async with get_session() as session:
            result = await session.execute(
                select(AIDeliveryAttempt)
                .where(
                    AIDeliveryAttempt.task_id == create_input.task_id,
                    AIDeliveryAttempt.delivery_intent == create_input.delivery_intent,
                    AIDeliveryAttempt.status == "pending",
                )
                .order_by(AIDeliveryAttempt.attempt_id.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return _orm_to_record(existing)

            attempt_id = f"delivery_attempt_{uuid4().hex}"
            now = _epoch_ms()
            created_ms = _datetime_to_epoch_ms(create_input.created_at)
            item = AIDeliveryAttempt(
                attempt_id=attempt_id,
                task_id=create_input.task_id,
                trace_id=create_input.trace_id,
                session_id=create_input.session_id,
                delivery_intent=create_input.delivery_intent,
                platform=create_input.platform,
                scene_type=create_input.scene_type,
                scene_id=create_input.scene_id,
                message_preview=create_input.message_preview,
                message_hash=create_input.message_hash,
                status="pending",
                diagnostics_json="{}",
                attempt_count=0,
                created_at=created_ms,
                updated_at=now,
            )
            session.add(item)
            await session.commit()
            reload = await session.execute(
                select(AIDeliveryAttempt).where(
                    AIDeliveryAttempt.attempt_id == attempt_id
                )
            )
            row = reload.scalar_one_or_none()
        if row is None:
            raise AIDeliveryAttemptRepositoryError
        return _orm_to_record(row)

    async def get_delivered_attempt(
        self,
        *,
        task_id: str,
        delivery_intent: str,
    ) -> AIDeliveryAttemptRecord | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIDeliveryAttempt)
                .where(
                    AIDeliveryAttempt.task_id == task_id,
                    AIDeliveryAttempt.delivery_intent == delivery_intent,
                    AIDeliveryAttempt.status == "delivered",
                )
                .order_by(
                    AIDeliveryAttempt.delivered_at.desc(),
                    AIDeliveryAttempt.attempt_id.desc(),
                )
                .limit(1)
            )
            item = result.scalar_one_or_none()
        if item is None:
            return None
        return _orm_to_record(item)

    async def mark_delivered(
        self,
        *,
        attempt_id: str,
        channel: str | None,
        remote_message_id: str | None,
        delivered_at: datetime,
    ) -> AIDeliveryAttemptRecord:
        delivered_ms = _datetime_to_epoch_ms(delivered_at)
        async with get_session() as session:
            await session.execute(
                update(AIDeliveryAttempt)
                .where(AIDeliveryAttempt.attempt_id == attempt_id)
                .values(
                    status="delivered",
                    reason=None,
                    channel=channel,
                    remote_message_id=remote_message_id,
                    attempt_count=AIDeliveryAttempt.attempt_count + 1,
                    delivered_at=delivered_ms,
                    failed_at=None,
                    updated_at=delivered_ms,
                )
            )
            await session.commit()
            result = await session.execute(
                select(AIDeliveryAttempt).where(
                    AIDeliveryAttempt.attempt_id == attempt_id
                )
            )
            item = result.scalar_one_or_none()
        if item is None:
            raise KeyError(attempt_id)
        return _orm_to_record(item)

    async def mark_failed(
        self,
        *,
        attempt_id: str,
        reason: str | None,
        diagnostics: dict[str, Any] | None,
        failed_at: datetime,
    ) -> AIDeliveryAttemptRecord:
        failed_ms = _datetime_to_epoch_ms(failed_at)
        diagnostics_json = json.dumps(
            sanitize_runtime_diagnostics(diagnostics),
            ensure_ascii=False,
            sort_keys=True,
        )
        async with get_session() as session:
            await session.execute(
                update(AIDeliveryAttempt)
                .where(AIDeliveryAttempt.attempt_id == attempt_id)
                .values(
                    status="failed",
                    reason=reason,
                    diagnostics_json=diagnostics_json,
                    attempt_count=AIDeliveryAttempt.attempt_count + 1,
                    delivered_at=None,
                    failed_at=failed_ms,
                    updated_at=failed_ms,
                )
            )
            await session.commit()
            result = await session.execute(
                select(AIDeliveryAttempt).where(
                    AIDeliveryAttempt.attempt_id == attempt_id
                )
            )
            item = result.scalar_one_or_none()
        if item is None:
            raise KeyError(attempt_id)
        return _orm_to_record(item)


def _orm_to_record(item: AIDeliveryAttempt) -> AIDeliveryAttemptRecord:
    return AIDeliveryAttemptRecord(
        attempt_id=item.attempt_id,
        task_id=item.task_id,
        trace_id=item.trace_id,
        session_id=item.session_id,
        delivery_intent=item.delivery_intent,
        platform=item.platform,
        scene_type=item.scene_type,
        scene_id=item.scene_id,
        message_preview=item.message_preview,
        message_hash=item.message_hash,
        status=cast("AIDeliveryAttemptStatus", item.status),
        reason=item.reason,
        diagnostics=_load_json_dict(item.diagnostics_json),
        channel=item.channel,
        remote_message_id=item.remote_message_id,
        attempt_count=item.attempt_count,
        delivered_at=_epoch_ms_to_datetime(item.delivered_at)
        if item.delivered_at is not None
        else None,
        failed_at=_epoch_ms_to_datetime(item.failed_at)
        if item.failed_at is not None
        else None,
        created_at=_epoch_ms_to_datetime(item.created_at),
        updated_at=_epoch_ms_to_datetime(item.updated_at),
    )


def _epoch_ms_to_datetime(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def _datetime_to_epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _load_json_dict(value: str | None) -> dict[str, object]:
    try:
        payload = json.loads(value or "{}")
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
