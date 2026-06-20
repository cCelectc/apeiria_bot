"""Persistence helpers for plugin governance state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session
from apeiria.db.models.governance import PluginState
from apeiria.db.runtime import database_runtime
from apeiria.exceptions import ResourceNotFoundError

if TYPE_CHECKING:
    from collections.abc import Collection

    from nonebot.plugin import Plugin


@dataclass(frozen=True)
class PluginStateRow:
    """Persisted plugin governance row."""

    module_name: str
    is_global_enabled: bool = True
    access_mode: str = "default_allow"
    protection_mode: str = "normal"
    ui_hidden_override: bool | None = None
    name: str | None = None
    description: str | None = None
    plugin_type: str = "normal"
    author: str | None = None
    version: str | None = None

    @property
    def plugin_module(self) -> str:
        return self.module_name

    @property
    def is_ui_hidden(self) -> bool:
        return bool(self.ui_hidden_override)


class PluginCatalogRepository:
    """Plugin governance persistence — async runtime + sync startup methods."""

    # ─── Startup-only sync methods (called before event loop) ───

    def get_persisted_plugin_modules_sync(self) -> set[str]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute("SELECT plugin_id FROM plugin_state").fetchall()
        return {str(row[0]) for row in rows}

    def delete_plugin_records_sync(self, module_names: "Collection[str]") -> list[str]:
        normalized = sorted(
            {m.strip() for m in module_names if isinstance(m, str) and m.strip()}
        )
        if not normalized:
            return []
        placeholders = ", ".join("?" for _ in normalized)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                f"SELECT plugin_id FROM plugin_state"
                f" WHERE plugin_id IN ({placeholders})",
                normalized,
            ).fetchall()
            existing = sorted(str(row[0]) for row in rows)
            if not existing:
                return []
            connection.executemany(
                "DELETE FROM plugin_state WHERE plugin_id = ?",
                [(m,) for m in existing],
            )
        return existing

    def _get_enabled_map_sync(self) -> dict[str, bool]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                "SELECT plugin_id, enabled FROM plugin_state"
            ).fetchall()
        return {str(row[0]): bool(row[1]) for row in rows}

    # ─── Runtime async methods (use SQLAlchemy session) ───

    async def get_persisted_plugin_modules(self) -> set[str]:
        async with get_session() as session:
            result = await session.execute(select(PluginState.plugin_id))
            return {row[0] for row in result.all()}

    async def get_enabled_map(self) -> dict[str, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(PluginState.plugin_id, PluginState.enabled)
            )
            return {row[0]: bool(row[1]) for row in result.all()}

    async def get_plugin_enabled(self, module_name: str) -> bool:
        row = await self.get_plugin_policy(module_name)
        return True if row is None else row.is_global_enabled

    async def get_plugin_info_map(self) -> dict[str, PluginStateRow]:
        async with get_session() as session:
            result = await session.execute(select(PluginState))
            rows = result.scalars().all()
        return {r.plugin_id: self._to_row(r) for r in rows}

    async def get_plugin_policy_map(self) -> dict[str, PluginStateRow]:
        return await self.get_plugin_info_map()

    async def get_plugin_policy(self, module_name: str) -> PluginStateRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(PluginState).where(PluginState.plugin_id == module_name)
            )
            model = result.scalars().first()
        if model is None:
            return None
        return self._to_row(model)

    async def set_plugin_enabled(self, module_name: str, *, enabled: bool) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(PluginState.enabled).where(PluginState.plugin_id == module_name)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise ResourceNotFoundError(module_name)
            if bool(existing) == enabled:
                return False
            await session.execute(
                update(PluginState)
                .where(PluginState.plugin_id == module_name)
                .values(enabled=1 if enabled else 0, updated_at=_now_iso())
            )
            await session.commit()
        return True

    async def delete_plugin_records(self, module_names: "Collection[str]") -> list[str]:
        return self.delete_plugin_records_sync(module_names)

    async def ensure_plugin_record_by_module_name(self, module_name: str) -> None:
        now = _now_iso()
        stmt = insert(PluginState).values(
            plugin_id=module_name,
            enabled=1,
            access_mode="default_allow",
            protection_mode="normal",
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=[PluginState.plugin_id])
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()

    async def ensure_plugin_record(self, plugin: "Plugin") -> None:
        await self.ensure_plugin_record_by_module_name(plugin.module_name)

    async def ensure_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str = "default_allow",
        protection_mode: str = "normal",
    ) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(PluginState.access_mode, PluginState.protection_mode).where(
                    PluginState.plugin_id == module_name
                )
            )
            existing = result.first()
            now = _now_iso()
            if existing is None:
                session.add(
                    PluginState(
                        plugin_id=module_name,
                        enabled=1,
                        access_mode=access_mode,
                        protection_mode=protection_mode,
                        updated_at=now,
                    )
                )
            else:
                next_access = (
                    access_mode
                    if existing[0] == "default_allow" and access_mode != "default_allow"
                    else existing[0]
                )
                next_protection = (
                    protection_mode
                    if existing[1] == "normal" and protection_mode != "normal"
                    else existing[1]
                )
                await session.execute(
                    update(PluginState)
                    .where(PluginState.plugin_id == module_name)
                    .values(
                        access_mode=next_access,
                        protection_mode=next_protection,
                        updated_at=now,
                    )
                )
            await session.commit()

    async def update_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str | None = None,
        protection_mode: str | None = None,
    ) -> None:
        existing = await self.get_plugin_policy(module_name)
        if existing is None:
            await self.ensure_plugin_policy(
                module_name,
                access_mode=access_mode or "default_allow",
                protection_mode=protection_mode or "normal",
            )
            return
        now = _now_iso()
        async with get_session() as session:
            await session.execute(
                update(PluginState)
                .where(PluginState.plugin_id == module_name)
                .values(
                    access_mode=access_mode or existing.access_mode,
                    protection_mode=protection_mode or existing.protection_mode,
                    updated_at=now,
                )
            )
            await session.commit()

    @staticmethod
    def _to_row(model: PluginState) -> PluginStateRow:
        return PluginStateRow(
            module_name=model.plugin_id,
            is_global_enabled=bool(model.enabled),
            access_mode=model.access_mode,
            protection_mode=model.protection_mode,
        )


plugin_catalog_repository = PluginCatalogRepository()
