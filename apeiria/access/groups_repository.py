"""Persistence helpers for group settings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apeiria.db.runtime import database_runtime


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class GroupStateRow:
    """Persisted per-group governance state."""

    group_id: str
    group_name: str | None = None
    bot_status: bool = True
    disabled_plugins: str = "[]"
    updated_at: str | None = None


class GroupRepository:
    """Own group-state persistence without relying on NoneBot ORM."""

    async def get_group(self, group_id: str) -> GroupStateRow | None:
        return self._get_group_sync(group_id)

    def _get_group_sync(self, group_id: str) -> GroupStateRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT
                    group_id,
                    group_name,
                    bot_enabled,
                    disabled_plugins_json,
                    updated_at
                FROM group_state
                WHERE group_id = ?
                """,
                (group_id,),
            ).fetchone()
        if row is None:
            return None
        return GroupStateRow(
            group_id=str(row[0]),
            group_name=str(row[1]) if row[1] is not None else None,
            bot_status=bool(row[2]),
            disabled_plugins=str(row[3]),
            updated_at=str(row[4]),
        )

    async def list_groups(self) -> list[GroupStateRow]:
        return self._list_groups_sync()

    def _list_groups_sync(self) -> list[GroupStateRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    group_id,
                    group_name,
                    bot_enabled,
                    disabled_plugins_json,
                    updated_at
                FROM group_state
                ORDER BY updated_at DESC, group_id ASC
                """
            ).fetchall()
        return [
            GroupStateRow(
                group_id=str(row[0]),
                group_name=str(row[1]) if row[1] is not None else None,
                bot_status=bool(row[2]),
                disabled_plugins=str(row[3]),
                updated_at=str(row[4]),
            )
            for row in rows
        ]

    async def save_group(self, row: GroupStateRow) -> None:
        self._save_group_sync(row)

    def _save_group_sync(self, row: GroupStateRow) -> None:
        updated_at = row.updated_at or _utcnow_text()
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO group_state (
                    group_id,
                    group_name,
                    bot_enabled,
                    disabled_plugins_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(group_id)
                DO UPDATE SET
                    group_name = excluded.group_name,
                    bot_enabled = excluded.bot_enabled,
                    disabled_plugins_json = excluded.disabled_plugins_json,
                    updated_at = excluded.updated_at
                """,
                (
                    row.group_id,
                    row.group_name,
                    1 if row.bot_status else 0,
                    row.disabled_plugins,
                    updated_at,
                ),
            )


group_repository = GroupRepository()
