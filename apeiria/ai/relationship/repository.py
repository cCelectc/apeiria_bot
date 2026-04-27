"""SQLite persistence for AI relationship state and events."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from apeiria.ai.relationship.scope import build_affinity_scope_key
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from collections.abc import Iterator
    from sqlite3 import Connection

    from apeiria.ai.relationship.models import AIRelationshipEventType


@dataclass
class AffinityRow:
    id: int
    affinity_id: str
    platform: str
    group_id: str | None
    scope_key: str
    user_id: str
    score: float
    mood_tags_json: str
    last_event_at: datetime
    last_decay_at: datetime | None


@dataclass(frozen=True)
class RelationshipEventRow:
    id: int
    event_id: str
    affinity_id: str
    platform: str
    group_id: str | None
    user_id: str
    event_type: str
    score_delta: float
    score_after: float
    mood_tag: str | None
    reason: str | None
    created_at: datetime


class RelationshipRepository:
    """Own low-level SQL operations for relationship persistence."""

    @contextmanager
    def transaction_sync(self) -> "Iterator[Connection]":
        with database_runtime.transaction_sync() as connection:
            yield connection

    def find_row(
        self,
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AffinityRow | None:
        with database_runtime.connect_sync() as connection:
            return self.find_row_with_connection(
                connection,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )

    def get_or_create_row(
        self,
        connection: "Connection",
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AffinityRow:
        row = self.find_row_with_connection(
            connection,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        if row is not None:
            return row

        scope_key = build_affinity_scope_key(group_id)
        now = utcnow()
        connection.execute(
            """
            INSERT INTO ai_affinity (
                affinity_id,
                platform,
                group_id,
                scope_key,
                user_id,
                score,
                mood_tags_json,
                last_event_at,
                last_decay_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, scope_key, user_id) DO NOTHING
            """,
            (
                f"aff_{uuid4().hex}",
                platform,
                group_id,
                scope_key,
                user_id,
                0.0,
                "[]",
                datetime_to_text(now),
                None,
            ),
        )
        row = self.find_row_with_connection(
            connection,
            platform=platform,
            group_id=group_id,
            user_id=user_id,
        )
        assert row is not None
        return row

    def find_row_with_connection(
        self,
        connection: "Connection",
        *,
        platform: str,
        group_id: str | None,
        user_id: str,
    ) -> AffinityRow | None:
        scope_key = build_affinity_scope_key(group_id)
        row = connection.execute(
            """
            SELECT
                id,
                affinity_id,
                platform,
                group_id,
                scope_key,
                user_id,
                score,
                mood_tags_json,
                last_event_at,
                last_decay_at
            FROM ai_affinity
            WHERE platform = ? AND scope_key = ? AND user_id = ?
            """,
            (platform, scope_key, user_id),
        ).fetchone()
        return None if row is None else row_to_affinity(row)

    def list_rows(
        self,
        *,
        limit: int,
    ) -> list[AffinityRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    affinity_id,
                    platform,
                    group_id,
                    scope_key,
                    user_id,
                    score,
                    mood_tags_json,
                    last_event_at,
                    last_decay_at
                FROM ai_affinity
                ORDER BY last_event_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row_to_affinity(row) for row in rows]

    def list_event_rows(
        self,
        *,
        affinity_id: str,
        limit: int,
    ) -> list[RelationshipEventRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    affinity_id,
                    platform,
                    group_id,
                    user_id,
                    event_type,
                    score_delta,
                    score_after,
                    mood_tag,
                    reason,
                    created_at
                FROM ai_relationship_event
                WHERE affinity_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (affinity_id, limit),
            ).fetchall()
        return [row_to_relationship_event(row) for row in rows]

    def update_row(self, connection: "Connection", row: AffinityRow) -> None:
        connection.execute(
            """
            UPDATE ai_affinity
            SET
                score = ?,
                mood_tags_json = ?,
                last_event_at = ?,
                last_decay_at = ?
            WHERE affinity_id = ?
            """,
            (
                row.score,
                row.mood_tags_json,
                datetime_to_text(row.last_event_at),
                datetime_to_text(row.last_decay_at),
                row.affinity_id,
            ),
        )

    def record_event(  # noqa: PLR0913
        self,
        connection: "Connection",
        *,
        affinity_id: str,
        platform: str,
        group_id: str | None,
        user_id: str,
        event_type: AIRelationshipEventType,
        score_delta: float,
        score_after: float,
        mood_tag: str | None,
        reason: str | None,
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO ai_relationship_event (
                event_id,
                affinity_id,
                platform,
                group_id,
                user_id,
                event_type,
                score_delta,
                score_after,
                mood_tag,
                reason,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"rel_evt_{uuid4().hex}",
                affinity_id,
                platform,
                group_id,
                user_id,
                event_type,
                score_delta,
                score_after,
                mood_tag,
                reason,
                datetime_to_text(created_at),
            ),
        )


def serialize_mood_tags(mood_tags: tuple[str, ...]) -> str:
    return json.dumps(mood_tags, ensure_ascii=False)


def deserialize_mood_tags(raw_json: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def optional_datetime_from_text(value: object | None) -> datetime | None:
    return None if value is None else datetime_from_text(value)


def row_to_affinity(row: tuple[object, ...]) -> AffinityRow:
    return AffinityRow(
        id=int(str(row[0])),
        affinity_id=str(row[1]),
        platform=str(row[2]),
        group_id=str(row[3]) if row[3] is not None else None,
        scope_key=str(row[4]),
        user_id=str(row[5]),
        score=float(str(row[6])),
        mood_tags_json=str(row[7] or "[]"),
        last_event_at=datetime_from_text(row[8]),
        last_decay_at=optional_datetime_from_text(row[9]),
    )


def row_to_relationship_event(row: tuple[object, ...]) -> RelationshipEventRow:
    return RelationshipEventRow(
        id=int(str(row[0])),
        event_id=str(row[1]),
        affinity_id=str(row[2]),
        platform=str(row[3]),
        group_id=str(row[4]) if row[4] is not None else None,
        user_id=str(row[5]),
        event_type=str(row[6]),
        score_delta=float(str(row[7])),
        score_after=float(str(row[8])),
        mood_tag=str(row[9]) if row[9] is not None else None,
        reason=str(row[10]) if row[10] is not None else None,
        created_at=datetime_from_text(row[11]),
    )
