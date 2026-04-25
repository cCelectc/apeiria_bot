"""Persistence helpers for plugin governance state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime
from apeiria.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from nonebot.plugin import Plugin


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class PluginStateRow:
    """Persisted plugin governance row."""

    module_name: str
    is_global_enabled: bool = True
    access_mode: str = "default_allow"
    required_level: int = 0
    protection_mode: str = "normal"
    ui_hidden_override: bool | None = None
    name: str | None = None
    description: str | None = None
    plugin_type: str = "normal"
    admin_level: int = 0
    author: str | None = None
    version: str | None = None

    @property
    def plugin_module(self) -> str:
        return self.module_name

    @property
    def is_ui_hidden(self) -> bool:
        return bool(self.ui_hidden_override)


class PluginCatalogRepository:
    """Own plugin governance persistence without relying on NoneBot ORM."""

    async def get_enabled_map(self) -> dict[str, bool]:
        return self._get_enabled_map_sync()

    def _get_enabled_map_sync(self) -> dict[str, bool]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                "SELECT plugin_id, enabled FROM plugin_state"
            ).fetchall()
        return {str(row[0]): bool(row[1]) for row in rows}

    async def get_plugin_enabled(self, module_name: str) -> bool:
        row = self._get_plugin_state_sync(module_name)
        return True if row is None else row.is_global_enabled

    async def get_plugin_info_map(self) -> dict[str, PluginStateRow]:
        return self._get_plugin_info_map_sync()

    def _get_plugin_info_map_sync(self) -> dict[str, PluginStateRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    plugin_id,
                    enabled,
                    access_mode,
                    required_level,
                    protection_mode,
                    ui_hidden_override
                FROM plugin_state
                """
            ).fetchall()
        return {
            str(row[0]): PluginStateRow(
                module_name=str(row[0]),
                is_global_enabled=bool(row[1]),
                access_mode=str(row[2]),
                required_level=int(row[3]),
                protection_mode=str(row[4]),
                ui_hidden_override=(
                    None if row[5] is None else bool(row[5])
                ),
            )
            for row in rows
        }

    async def set_plugin_enabled(self, module_name: str, *, enabled: bool) -> bool:
        return self._set_plugin_enabled_sync(module_name, enabled=enabled)

    def _set_plugin_enabled_sync(self, module_name: str, *, enabled: bool) -> bool:
        with database_runtime.connect_sync() as connection:
            existing = connection.execute(
                "SELECT enabled FROM plugin_state WHERE plugin_id = ?",
                (module_name,),
            ).fetchone()
            if existing is None:
                raise ResourceNotFoundError(module_name)
            changed = bool(existing[0]) != enabled
            if not changed:
                return False
            connection.execute(
                """
                UPDATE plugin_state
                SET enabled = ?, updated_at = ?
                WHERE plugin_id = ?
                """,
                (1 if enabled else 0, _utcnow_text(), module_name),
            )
        return True

    async def ensure_plugin_record_by_module_name(self, module_name: str) -> None:
        self._ensure_plugin_record_sync(module_name)

    async def ensure_plugin_record(self, plugin: Plugin) -> None:
        await self.ensure_plugin_record_by_module_name(plugin.module_name)

    def _ensure_plugin_record_sync(self, module_name: str) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO plugin_state (
                    plugin_id,
                    enabled,
                    access_mode,
                    required_level,
                    protection_mode,
                    updated_at
                ) VALUES (?, 1, 'default_allow', 0, 'normal', ?)
                ON CONFLICT(plugin_id) DO NOTHING
                """,
                (module_name, _utcnow_text()),
            )

    async def get_plugin_policy_map(self) -> dict[str, PluginStateRow]:
        return await self.get_plugin_info_map()

    async def get_plugin_policy(
        self,
        module_name: str,
    ) -> PluginStateRow | None:
        return self._get_plugin_state_sync(module_name)

    def _get_plugin_state_sync(self, module_name: str) -> PluginStateRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT
                    plugin_id,
                    enabled,
                    access_mode,
                    required_level,
                    protection_mode,
                    ui_hidden_override
                FROM plugin_state
                WHERE plugin_id = ?
                """,
                (module_name,),
            ).fetchone()
        if row is None:
            return None
        return PluginStateRow(
            module_name=str(row[0]),
            is_global_enabled=bool(row[1]),
            access_mode=str(row[2]),
            required_level=int(row[3]),
            protection_mode=str(row[4]),
            ui_hidden_override=None if row[5] is None else bool(row[5]),
        )

    async def ensure_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str = "default_allow",
        required_level: int = 0,
        protection_mode: str = "normal",
    ) -> None:
        self._ensure_plugin_policy_sync(
            module_name,
            access_mode,
            required_level,
            protection_mode,
        )

    def _ensure_plugin_policy_sync(
        self,
        module_name: str,
        access_mode: str,
        required_level: int,
        protection_mode: str,
    ) -> None:
        with database_runtime.connect_sync() as connection:
            existing = connection.execute(
                """
                SELECT access_mode, required_level, protection_mode
                FROM plugin_state
                WHERE plugin_id = ?
                """,
                (module_name,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO plugin_state (
                        plugin_id,
                        enabled,
                        access_mode,
                        required_level,
                        protection_mode,
                        updated_at
                    ) VALUES (?, 1, ?, ?, ?, ?)
                    """,
                    (
                        module_name,
                        access_mode,
                        required_level,
                        protection_mode,
                        _utcnow_text(),
                    ),
                )
                return
            next_access_mode = (
                access_mode
                if (
                    str(existing[0]) == "default_allow"
                    and access_mode != "default_allow"
                )
                else str(existing[0])
            )
            next_required_level = (
                required_level
                if int(existing[1]) == 0 and required_level > 0
                else int(existing[1])
            )
            next_protection_mode = (
                protection_mode
                if str(existing[2]) == "normal" and protection_mode != "normal"
                else str(existing[2])
            )
            connection.execute(
                """
                UPDATE plugin_state
                SET
                    access_mode = ?,
                    required_level = ?,
                    protection_mode = ?,
                    updated_at = ?
                WHERE plugin_id = ?
                """,
                (
                    next_access_mode,
                    next_required_level,
                    next_protection_mode,
                    _utcnow_text(),
                    module_name,
                ),
            )

    async def update_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str | None = None,
        required_level: int | None = None,
        protection_mode: str | None = None,
    ) -> None:
        self._update_plugin_policy_sync(
            module_name,
            access_mode,
            required_level,
            protection_mode,
        )

    def _update_plugin_policy_sync(
        self,
        module_name: str,
        access_mode: str | None,
        required_level: int | None,
        protection_mode: str | None,
    ) -> None:
        existing = self._get_plugin_state_sync(module_name)
        if existing is None:
            self._ensure_plugin_policy_sync(
                module_name,
                access_mode or "default_allow",
                required_level or 0,
                protection_mode or "normal",
            )
            return
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE plugin_state
                SET access_mode = ?,
                    required_level = ?,
                    protection_mode = ?,
                    updated_at = ?
                WHERE plugin_id = ?
                """,
                (
                    access_mode if access_mode is not None else existing.access_mode,
                    (
                        required_level
                        if required_level is not None
                        else existing.required_level
                    ),
                    (
                        protection_mode
                        if protection_mode is not None
                        else existing.protection_mode
                    ),
                    _utcnow_text(),
                    module_name,
                ),
            )


plugin_catalog_repository = PluginCatalogRepository()
