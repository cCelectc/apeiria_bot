"""Async SQLAlchemy repository for managed AI session state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session as SyncSession

from apeiria.app.ai.sessions.models import (
    AISessionManagementRecord,
    AISessionManagementUpdate,
    AISessionMessageType,
    AISessionSourceIdentity,
    NormalizedAISessionIdentity,
    UnknownAISessionPersonaError,
)
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_engine, get_session
from apeiria.db.models.ai_session import AIManagedSession


@dataclass(frozen=True)
class AISessionManagementRepository:
    """Own SQL operations for v1 managed AI session records."""

    async def ensure_session(
        self,
        source_identity: AISessionSourceIdentity,
        *,
        actor_id: str | None = None,
        observed_at: datetime | None = None,
    ) -> AISessionManagementRecord:
        now = int((observed_at or _utcnow()).timestamp() * 1000)
        identity = source_identity.identity
        stmt = insert(AIManagedSession).values(
            session_id=identity.session_id,
            platform_id=identity.platform_id,
            platform_type=identity.platform_type,
            message_type=identity.message_type,
            subject_id=identity.subject_id,
            source_labels_json=_serialize_json_payload(source_identity.source_labels),
            diagnostic_raw_ids_json=_serialize_json_payload(
                source_identity.diagnostic_raw_ids
            ),
            ai_enabled=1,
            last_observed_at=now,
            created_at=now,
            updated_at=now,
            audit_created_by=actor_id,
            audit_updated_by=actor_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AIManagedSession.session_id],
            set_={
                "platform_id": stmt.excluded.platform_id,
                "platform_type": stmt.excluded.platform_type,
                "message_type": stmt.excluded.message_type,
                "subject_id": stmt.excluded.subject_id,
                "source_labels_json": stmt.excluded.source_labels_json,
                "diagnostic_raw_ids_json": stmt.excluded.diagnostic_raw_ids_json,
                "last_observed_at": stmt.excluded.last_observed_at,
                "updated_at": stmt.excluded.updated_at,
                "audit_updated_by": stmt.excluded.audit_updated_by,
            },
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()
            result = await session.execute(
                select(AIManagedSession).where(
                    AIManagedSession.session_id == identity.session_id
                )
            )
            row = result.scalar_one()
        return _row_to_record(row)

    async def get_session(
        self,
        session_id: str,
    ) -> AISessionManagementRecord | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIManagedSession).where(
                    AIManagedSession.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()
        return None if row is None else _row_to_record(row)

    def get_session_sync(
        self,
        session_id: str,
    ) -> AISessionManagementRecord | None:
        """Synchronously load one session for sync policy boundaries."""

        with SyncSession(get_engine().sync_engine) as session:
            result = session.execute(
                select(AIManagedSession).where(
                    AIManagedSession.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()
        return None if row is None else _row_to_record(row)

    async def list_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list[AISessionManagementRecord]:
        from sqlalchemy import func

        async with get_session() as session:
            result = await session.execute(
                select(AIManagedSession)
                .order_by(
                    func.coalesce(
                        AIManagedSession.last_observed_at,
                        AIManagedSession.updated_at,
                    ).desc(),
                    AIManagedSession.session_id.desc(),
                )
                .limit(limit)
            )
            rows = result.scalars().all()
        return [_row_to_record(r) for r in rows]

    async def update_session(
        self,
        *,
        session_id: str,
        update: AISessionManagementUpdate,
    ) -> AISessionManagementRecord | None:
        if update.updates_persona and update.normalized_persona_id is not None:
            await _ensure_persona_exists(update.normalized_persona_id)

        values: dict[str, object] = {}
        if update.ai_enabled is not None:
            values["ai_enabled"] = 1 if update.ai_enabled else 0
        if update.updates_persona:
            values["persona_id"] = update.normalized_persona_id
        values["updated_at"] = _epoch_ms()
        values["audit_updated_by"] = update.actor_id

        async with get_session() as session:
            await session.execute(
                sa_update(AIManagedSession)
                .where(AIManagedSession.session_id == session_id)
                .values(**values)
            )
            await session.commit()
            result = await session.execute(
                select(AIManagedSession).where(
                    AIManagedSession.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()
        return None if row is None else _row_to_record(row)

    async def mark_context_reset(
        self,
        *,
        session_id: str,
        actor_id: str | None = None,
        reset_at: datetime | None = None,
    ) -> AISessionManagementRecord | None:
        now_ms = int((reset_at or _utcnow()).timestamp() * 1000)
        async with get_session() as session:
            await session.execute(
                sa_update(AIManagedSession)
                .where(AIManagedSession.session_id == session_id)
                .values(
                    context_reset_at=now_ms,
                    context_reset_by=actor_id,
                    updated_at=now_ms,
                    audit_updated_by=actor_id,
                )
            )
            await session.commit()
            result = await session.execute(
                select(AIManagedSession).where(
                    AIManagedSession.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()
        return None if row is None else _row_to_record(row)


def _row_to_record(row: AIManagedSession) -> AISessionManagementRecord:
    identity = NormalizedAISessionIdentity(
        session_id=row.session_id,
        platform_id=row.platform_id,
        platform_type=row.platform_type,
        message_type=cast("AISessionMessageType", row.message_type),
        subject_id=row.subject_id,
    )
    return AISessionManagementRecord(
        session_id=identity.session_id,
        source_identity=AISessionSourceIdentity(
            identity=identity,
            source_labels=_deserialize_string_mapping(row.source_labels_json),
            diagnostic_raw_ids=_deserialize_string_mapping(row.diagnostic_raw_ids_json),
        ),
        ai_enabled=bool(row.ai_enabled),
        persona_id=row.persona_id,
        context_reset_at=_optional_epoch_ms_to_datetime(row.context_reset_at),
        context_reset_by=row.context_reset_by,
        last_observed_at=_optional_epoch_ms_to_datetime(row.last_observed_at),
        last_user_message_at=_optional_epoch_ms_to_datetime(row.last_user_message_at),
        last_ai_message_at=_optional_epoch_ms_to_datetime(row.last_ai_message_at),
        created_at=_epoch_ms_to_datetime(row.created_at),
        updated_at=_epoch_ms_to_datetime(row.updated_at),
        audit_created_by=row.audit_created_by,
        audit_updated_by=row.audit_updated_by,
    )


async def _ensure_persona_exists(persona_id: str) -> None:
    from apeiria.db.models.ai_persona import AIPersona

    async with get_session() as session:
        result = await session.execute(
            select(AIPersona.persona_id).where(AIPersona.persona_id == persona_id)
        )
        row = result.scalar_one_or_none()
    if row is None:
        raise UnknownAISessionPersonaError.for_persona_id(persona_id)


def _deserialize_string_mapping(value: str | None) -> dict[str, str]:
    if value is None:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(item) for key, item in payload.items()}


def _serialize_json_payload(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _epoch_ms_to_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _optional_epoch_ms_to_datetime(ms: int | None) -> datetime | None:
    if ms is None:
        return None
    return _epoch_ms_to_datetime(ms)


__all__ = ["AISessionManagementRepository"]
