"""SQLite persistence for AI person profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from apeiria.db.runtime import database_runtime


@dataclass
class PersonProfileRow:
    id: int
    person_id: str
    platform: str
    user_id: str
    person_name: str | None
    nickname: str | None
    name_reason: str | None
    memory_points_json: str
    is_known: bool
    know_since: datetime | None
    last_interaction: datetime
    created_at: datetime
    updated_at: datetime


class PersonProfileRepository:
    """Own low-level SQL operations for person profile persistence."""

    def get_profile_row_by_id(
        self,
        *,
        person_id: str,
    ) -> PersonProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE person_id = ?",
                (person_id,),
            ).fetchone()
        return None if row is None else row_to_person_profile(row)

    def get_profile_row(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> PersonProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE platform = ? AND user_id = ?",
                (platform, user_id),
            ).fetchone()
        return None if row is None else row_to_person_profile(row)

    def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> PersonProfileRow:
        row = self.get_profile_row(platform=platform, user_id=user_id)
        if row is not None:
            return row

        now = utcnow()
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ai_person_profile (
                    person_id,
                    platform,
                    user_id,
                    memory_points_json,
                    is_known,
                    last_interaction,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"person_{uuid4().hex}",
                    platform,
                    user_id,
                    "[]",
                    0,
                    datetime_to_text(now),
                    datetime_to_text(now),
                    datetime_to_text(now),
                ),
            )
            row_id = int(cursor.lastrowid or 0)
            inserted = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE id = ?",
                (row_id,),
            ).fetchone()
        assert inserted is not None
        return row_to_person_profile(inserted)

    def list_profile_rows(
        self,
        *,
        limit: int = 50,
    ) -> list[PersonProfileRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_PROFILE_FIELDS
                + """
                ORDER BY last_interaction DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row_to_person_profile(row) for row in rows]

    def update_profile_row(self, row: PersonProfileRow) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_person_profile
                SET
                    person_name = ?,
                    nickname = ?,
                    name_reason = ?,
                    memory_points_json = ?,
                    is_known = ?,
                    know_since = ?,
                    last_interaction = ?,
                    updated_at = ?
                WHERE person_id = ?
                """,
                (
                    row.person_name,
                    row.nickname,
                    row.name_reason,
                    row.memory_points_json,
                    1 if row.is_known else 0,
                    datetime_to_text(row.know_since),
                    datetime_to_text(row.last_interaction),
                    datetime_to_text(row.updated_at),
                    row.person_id,
                ),
            )

    def delete_profile(
        self,
        *,
        person_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_person_profile WHERE person_id = ?",
                (person_id,),
            )
            return int(cursor.rowcount or 0) > 0


_SELECT_PROFILE_FIELDS = """
SELECT
    id,
    person_id,
    platform,
    user_id,
    person_name,
    nickname,
    name_reason,
    memory_points_json,
    is_known,
    know_since,
    last_interaction,
    created_at,
    updated_at
FROM ai_person_profile
"""


def row_to_person_profile(row: tuple[object, ...]) -> PersonProfileRow:
    return PersonProfileRow(
        id=int(str(row[0])),
        person_id=str(row[1]),
        platform=str(row[2]),
        user_id=str(row[3]),
        person_name=str(row[4]) if row[4] is not None else None,
        nickname=str(row[5]) if row[5] is not None else None,
        name_reason=str(row[6]) if row[6] is not None else None,
        memory_points_json=str(row[7] or "[]"),
        is_known=bool(row[8]),
        know_since=optional_datetime_from_text(row[9]),
        last_interaction=datetime_from_text(row[10]),
        created_at=datetime_from_text(row[11]),
        updated_at=datetime_from_text(row[12]),
    )


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
