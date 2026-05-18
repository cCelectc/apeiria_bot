"""Persistence helpers for access-related state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apeiria.db.runtime import database_runtime
from apeiria.utils.group_state import decode_disabled_plugins


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AccessRuleRow:
    """Persisted explicit access rule."""

    subject_type: str
    subject_id: str
    plugin_module: str
    effect: str
    note: str | None = None


class AccessRepository:
    """Own access persistence without relying on NoneBot ORM."""

    async def get_group_bot_enabled(self, group_id: str) -> bool:
        return self._get_group_bot_enabled_sync(group_id)

    def _get_group_bot_enabled_sync(self, group_id: str) -> bool:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT bot_enabled
                FROM group_state
                WHERE group_id = ?
                """,
                (group_id,),
            ).fetchone()
        return row is None or bool(row[0])

    async def get_group_disabled_plugins(self, group_id: str) -> list[str]:
        return self._get_group_disabled_plugins_sync(group_id)

    def _get_group_disabled_plugins_sync(self, group_id: str) -> list[str]:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT disabled_plugins_json
                FROM group_state
                WHERE group_id = ?
                """,
                (group_id,),
            ).fetchone()
        return decode_disabled_plugins(row[0] if row is not None else None)

    async def list_access_rules(self) -> list[AccessRuleRow]:
        return self._list_access_rules_sync()

    def _list_access_rules_sync(self) -> list[AccessRuleRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT subject_type, subject_id, plugin_id, effect, note
                FROM access_rule
                ORDER BY subject_type ASC, subject_id ASC, plugin_id ASC
                """
            ).fetchall()
        return [
            AccessRuleRow(
                subject_type=str(row[0]),
                subject_id=str(row[1]),
                plugin_module=str(row[2]),
                effect=str(row[3]),
                note=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]

    async def get_explicit_rules_for_subjects(
        self,
        *,
        plugin_module: str,
        user_id: str,
        group_id: str | None,
    ) -> list[AccessRuleRow]:
        return self._get_explicit_rules_for_subjects_sync(
            plugin_module,
            user_id,
            group_id,
        )

    def _get_explicit_rules_for_subjects_sync(
        self,
        plugin_module: str,
        user_id: str,
        group_id: str | None,
    ) -> list[AccessRuleRow]:
        clauses = ["(subject_type = ? AND subject_id = ?)"]
        params: list[object] = ["user", user_id, plugin_module]
        if group_id is not None:
            clauses.append("(subject_type = ? AND subject_id = ?)")
            params = ["user", user_id, "group", group_id, plugin_module]
        where_sql = " OR ".join(clauses)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                f"""
                SELECT subject_type, subject_id, plugin_id, effect, note
                FROM access_rule
                WHERE ({where_sql}) AND plugin_id = ?
                """,
                tuple(params),
            ).fetchall()
        return [
            AccessRuleRow(
                subject_type=str(row[0]),
                subject_id=str(row[1]),
                plugin_module=str(row[2]),
                effect=str(row[3]),
                note=str(row[4]) if row[4] is not None else None,
            )
            for row in rows
        ]

    async def upsert_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
        effect: str,
        note: str | None = None,
    ) -> None:
        self._upsert_access_rule_sync(
            subject_type,
            subject_id,
            plugin_module,
            effect,
            note,
        )

    def _upsert_access_rule_sync(
        self,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
        effect: str,
        note: str | None,
    ) -> None:
        timestamp = _utcnow_text()
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO access_rule (
                    subject_type,
                    subject_id,
                    plugin_id,
                    effect,
                    note,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_type, subject_id, plugin_id)
                DO UPDATE SET
                    effect = excluded.effect,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (
                    subject_type,
                    subject_id,
                    plugin_module,
                    effect,
                    note,
                    timestamp,
                    timestamp,
                ),
            )

    async def delete_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        return self._delete_access_rule_sync(
            subject_type,
            subject_id,
            plugin_module,
        )

    def _delete_access_rule_sync(
        self,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                DELETE FROM access_rule
                WHERE subject_type = ? AND subject_id = ? AND plugin_id = ?
                """,
                (subject_type, subject_id, plugin_module),
            )
        return cursor.rowcount > 0


access_repository = AccessRepository()
