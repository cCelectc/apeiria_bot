"""SQLite persistence for AI profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.ai.profile.models import AIProfileNameSource, AIProfileNameVisibility

_NAME_SOURCES = frozenset({"manual", "self_introduced", "platform", "inferred"})
_NAME_VISIBILITIES = frozenset({"private_only", "public_allowed", "disabled"})


@dataclass
class ProfileRow:
    id: int
    profile_id: str
    platform: str
    user_id: str
    display_name: str | None
    preferred_name: str | None
    name_source: AIProfileNameSource | None
    name_visibility: AIProfileNameVisibility
    profile_enabled: bool
    last_interaction_at: datetime
    created_at: datetime
    updated_at: datetime


class ProfileRepository:
    """Own low-level SQL operations for profile persistence."""

    def get_profile_row_by_id(
        self,
        *,
        profile_id: str,
    ) -> ProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return None if row is None else row_to_profile(row)

    def get_profile_row(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> ProfileRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_PROFILE_FIELDS + " WHERE platform = ? AND user_id = ?",
                (platform, user_id),
            ).fetchone()
        return None if row is None else row_to_profile(row)

    def ensure_profile(
        self,
        *,
        platform: str,
        user_id: str,
    ) -> ProfileRow:
        row = self.get_profile_row(platform=platform, user_id=user_id)
        if row is not None:
            return row

        now = utcnow()
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ai_profile (
                    profile_id,
                    platform,
                    user_id,
                    name_visibility,
                    profile_enabled,
                    last_interaction_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"profile_{uuid4().hex}",
                    platform,
                    user_id,
                    "public_allowed",
                    1,
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
        return row_to_profile(inserted)

    def list_profile_rows(
        self,
        *,
        limit: int = 50,
    ) -> list[ProfileRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_PROFILE_FIELDS
                + """
                ORDER BY last_interaction_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row_to_profile(row) for row in rows]

    def update_profile_row(self, row: ProfileRow) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_profile
                SET
                    display_name = ?,
                    preferred_name = ?,
                    name_source = ?,
                    name_visibility = ?,
                    profile_enabled = ?,
                    last_interaction_at = ?,
                    updated_at = ?
                WHERE profile_id = ?
                """,
                (
                    row.display_name,
                    row.preferred_name,
                    row.name_source,
                    row.name_visibility,
                    1 if row.profile_enabled else 0,
                    datetime_to_text(row.last_interaction_at),
                    datetime_to_text(row.updated_at),
                    row.profile_id,
                ),
            )

    def delete_profile(
        self,
        *,
        profile_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_profile WHERE profile_id = ?",
                (profile_id,),
            )
            return int(cursor.rowcount or 0) > 0


_SELECT_PROFILE_FIELDS = """
SELECT
    id,
    profile_id,
    platform,
    user_id,
    display_name,
    preferred_name,
    name_source,
    name_visibility,
    profile_enabled,
    last_interaction_at,
    created_at,
    updated_at
FROM ai_profile
"""


def row_to_profile(row: tuple[object, ...]) -> ProfileRow:
    return ProfileRow(
        id=int(str(row[0])),
        profile_id=str(row[1]),
        platform=str(row[2]),
        user_id=str(row[3]),
        display_name=str(row[4]) if row[4] is not None else None,
        preferred_name=str(row[5]) if row[5] is not None else None,
        name_source=_coerce_name_source(row[6]),
        name_visibility=_coerce_name_visibility(row[7]),
        profile_enabled=bool(row[8]),
        last_interaction_at=datetime_from_text(row[9]),
        created_at=datetime_from_text(row[10]),
        updated_at=datetime_from_text(row[11]),
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_name_source(value: object) -> "AIProfileNameSource | None":
    text = str(value) if value is not None else ""
    if text in _NAME_SOURCES:
        return cast("AIProfileNameSource", text)
    return None


def _coerce_name_visibility(value: object) -> "AIProfileNameVisibility":
    text = str(value) if value is not None else ""
    if text in _NAME_VISIBILITIES:
        return cast("AIProfileNameVisibility", text)
    return "public_allowed"


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
