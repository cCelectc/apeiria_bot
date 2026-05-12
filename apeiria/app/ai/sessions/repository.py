"""SQLite repository for managed AI session state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from apeiria.app.ai.sessions.models import (
    AISessionManagementRecord,
    AISessionManagementUpdate,
    AISessionMessageType,
    AISessionSourceIdentity,
    NormalizedAISessionIdentity,
    UnknownAISessionPersonaError,
)
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection


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
        timestamp = observed_at or _utcnow()
        timestamp_text = _datetime_to_text(timestamp)
        identity = source_identity.identity
        with database_runtime.transaction_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_managed_session (
                    session_id,
                    platform_id,
                    platform_type,
                    message_type,
                    subject_id,
                    source_labels_json,
                    diagnostic_raw_ids_json,
                    ai_enabled,
                    last_observed_at,
                    created_at,
                    updated_at,
                    audit_created_by,
                    audit_updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    platform_id = excluded.platform_id,
                    platform_type = excluded.platform_type,
                    message_type = excluded.message_type,
                    subject_id = excluded.subject_id,
                    source_labels_json = excluded.source_labels_json,
                    diagnostic_raw_ids_json = excluded.diagnostic_raw_ids_json,
                    last_observed_at = excluded.last_observed_at,
                    updated_at = excluded.updated_at,
                    audit_updated_by = excluded.audit_updated_by
                """,
                (
                    identity.session_id,
                    identity.platform_id,
                    identity.platform_type,
                    identity.message_type,
                    identity.subject_id,
                    _serialize_json_payload(source_identity.source_labels),
                    _serialize_json_payload(source_identity.diagnostic_raw_ids),
                    1,
                    timestamp_text,
                    timestamp_text,
                    timestamp_text,
                    actor_id,
                    actor_id,
                ),
            )
            row = _select_session_row(connection, session_id=identity.session_id)
        assert row is not None
        return _row_to_record(row)

    async def get_session(
        self,
        session_id: str,
    ) -> AISessionManagementRecord | None:
        return self.get_session_sync(session_id)

    def get_session_sync(
        self,
        session_id: str,
    ) -> AISessionManagementRecord | None:
        """Synchronously load one session for sync policy boundaries."""

        with database_runtime.connect_sync() as connection:
            row = _select_session_row(connection, session_id=session_id)
        return None if row is None else _row_to_record(row)

    async def list_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list[AISessionManagementRecord]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_MANAGED_SESSION_FIELDS
                + """
                ORDER BY
                    COALESCE(last_observed_at, updated_at) DESC,
                    id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    async def update_session(
        self,
        *,
        session_id: str,
        update: AISessionManagementUpdate,
    ) -> AISessionManagementRecord | None:
        if update.updates_persona and update.normalized_persona_id is not None:
            _ensure_persona_exists(update.normalized_persona_id)

        assignments: list[str] = []
        values: list[object] = []
        if update.ai_enabled is not None:
            assignments.append("ai_enabled = ?")
            values.append(1 if update.ai_enabled else 0)
        if update.updates_persona:
            assignments.append("persona_id = ?")
            values.append(update.normalized_persona_id)
        assignments.extend(["updated_at = ?", "audit_updated_by = ?"])
        values.extend([_datetime_to_text(_utcnow()), update.actor_id])
        values.append(session_id)

        with database_runtime.transaction_sync() as connection:
            connection.execute(
                f"""
                UPDATE ai_managed_session
                SET {", ".join(assignments)}
                WHERE session_id = ?
                """,
                tuple(values),
            )
            row = _select_session_row(connection, session_id=session_id)
        return None if row is None else _row_to_record(row)

    async def mark_context_reset(
        self,
        *,
        session_id: str,
        actor_id: str | None = None,
        reset_at: datetime | None = None,
    ) -> AISessionManagementRecord | None:
        timestamp = reset_at or _utcnow()
        timestamp_text = _datetime_to_text(timestamp)
        with database_runtime.transaction_sync() as connection:
            connection.execute(
                """
                UPDATE ai_managed_session
                SET
                    context_reset_at = ?,
                    context_reset_by = ?,
                    updated_at = ?,
                    audit_updated_by = ?
                WHERE session_id = ?
                """,
                (
                    timestamp_text,
                    actor_id,
                    timestamp_text,
                    actor_id,
                    session_id,
                ),
            )
            row = _select_session_row(connection, session_id=session_id)
        return None if row is None else _row_to_record(row)


_SELECT_MANAGED_SESSION_FIELDS = """
SELECT
    id,
    session_id,
    platform_id,
    platform_type,
    message_type,
    subject_id,
    source_labels_json,
    diagnostic_raw_ids_json,
    ai_enabled,
    persona_id,
    context_reset_at,
    context_reset_by,
    last_observed_at,
    last_user_message_at,
    last_ai_message_at,
    created_at,
    updated_at,
    audit_created_by,
    audit_updated_by
FROM ai_managed_session
"""


def _select_session_row(
    connection: "Connection",
    *,
    session_id: str,
) -> tuple[object, ...] | None:
    return connection.execute(
        _SELECT_MANAGED_SESSION_FIELDS + " WHERE session_id = ?",
        (session_id,),
    ).fetchone()


def _row_to_record(row: tuple[object, ...]) -> AISessionManagementRecord:
    identity = NormalizedAISessionIdentity(
        session_id=str(row[1]),
        platform_id=str(row[2]),
        platform_type=str(row[3]),
        message_type=cast("AISessionMessageType", str(row[4])),
        subject_id=str(row[5]),
    )
    return AISessionManagementRecord(
        session_id=identity.session_id,
        source_identity=AISessionSourceIdentity(
            identity=identity,
            source_labels=_deserialize_string_mapping(row[6]),
            diagnostic_raw_ids=_deserialize_string_mapping(row[7]),
        ),
        ai_enabled=bool(row[8]),
        persona_id=str(row[9]) if row[9] is not None else None,
        context_reset_at=_datetime_from_optional_text(row[10]),
        context_reset_by=str(row[11]) if row[11] is not None else None,
        last_observed_at=_datetime_from_optional_text(row[12]),
        last_user_message_at=_datetime_from_optional_text(row[13]),
        last_ai_message_at=_datetime_from_optional_text(row[14]),
        created_at=_datetime_from_text(row[15]),
        updated_at=_datetime_from_text(row[16]),
        audit_created_by=str(row[17]) if row[17] is not None else None,
        audit_updated_by=str(row[18]) if row[18] is not None else None,
    )


def _ensure_persona_exists(persona_id: str) -> None:
    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM ai_persona
            WHERE persona_id = ?
            """,
            (persona_id,),
        ).fetchone()
    if row is None:
        raise UnknownAISessionPersonaError.for_persona_id(persona_id)


def _deserialize_string_mapping(value: object) -> dict[str, str]:
    if value is None:
        return {}
    try:
        payload = json.loads(str(value))
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


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _datetime_from_optional_text(value: object) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_text(value)


__all__ = ["AISessionManagementRepository"]
