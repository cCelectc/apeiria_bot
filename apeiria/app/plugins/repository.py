"""Persistence helpers for plugin catalog state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from apeiria.infra.db.models.plugin_info import PluginInfo
from apeiria.infra.db.models.plugin_policy import PluginPolicyEntry
from apeiria.shared.exceptions import ResourceNotFoundError
from apeiria.shared.plugin_metadata import PluginExtraData

if TYPE_CHECKING:
    from nonebot.plugin import Plugin


class PluginCatalogRepository:
    """Own ORM access for plugin catalog persistence."""

    async def get_enabled_map(self) -> dict[str, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(PluginInfo.module_name, PluginInfo.is_global_enabled)
            )
            rows = result.all()
        return {row[0]: row[1] for row in rows}

    async def get_plugin_enabled(self, module_name: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(PluginInfo.is_global_enabled).where(
                    PluginInfo.module_name == module_name
                )
            )
            value = result.scalar_one_or_none()
        return True if value is None else bool(value)

    async def get_plugin_info_map(self) -> dict[str, PluginInfo]:
        """Return persisted plugin info indexed by module name."""
        async with get_session() as session:
            result = await session.execute(select(PluginInfo))
            rows = result.scalars().all()
        return {row.module_name: row for row in rows}

    async def set_plugin_enabled(self, module_name: str, *, enabled: bool) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(PluginInfo).where(PluginInfo.module_name == module_name)
            )
            record = result.scalar_one_or_none()
            if record is None:
                raise ResourceNotFoundError(module_name)
            changed = record.is_global_enabled != enabled
            if not changed:
                return False
            record.is_global_enabled = enabled
            await session.commit()
        return True

    async def ensure_plugin_record_by_module_name(self, module_name: str) -> None:
        """Ensure a minimal plugin record exists for unloaded-but-managed plugins."""
        async with get_session() as session:
            result = await session.execute(
                select(PluginInfo).where(PluginInfo.module_name == module_name)
            )
            record = result.scalar_one_or_none()
            if record is not None:
                return

            session.add(
                PluginInfo(
                    module_name=module_name,
                    name=module_name,
                )
            )
            await session.commit()

    async def ensure_plugin_record(self, plugin: Plugin) -> None:
        meta = plugin.metadata
        extra: PluginExtraData | None = None
        if meta and meta.extra:
            extra = PluginExtraData.from_extra(meta.extra)
        name = (
            extra.ui.label
            if extra is not None and extra.ui.label
            else meta.name
            if meta
            else plugin.name
        )

        async with get_session() as session:
            result = await session.execute(
                select(PluginInfo).where(PluginInfo.module_name == plugin.module_name)
            )
            record = result.scalar_one_or_none()
            if record is None:
                session.add(
                    PluginInfo(
                        module_name=plugin.module_name,
                        name=name,
                        description=meta.description if meta else None,
                        usage=meta.usage if meta else None,
                        plugin_type=extra.plugin_type.value if extra else "normal",
                        admin_level=extra.admin_level if extra else 0,
                        author=extra.author if extra else None,
                        version=extra.version if extra else None,
                    )
                )
                await session.commit()
                return

            record.name = name
            record.description = meta.description if meta else None
            record.usage = meta.usage if meta else None
            record.plugin_type = extra.plugin_type.value if extra else "normal"
            record.admin_level = extra.admin_level if extra else 0
            record.author = extra.author if extra else None
            record.version = extra.version if extra else None
            await session.commit()

    async def get_plugin_policy_map(self) -> dict[str, PluginPolicyEntry]:
        async with get_session() as session:
            result = await session.execute(select(PluginPolicyEntry))
            rows = result.scalars().all()
        return {row.plugin_module: row for row in rows}

    async def get_plugin_policy(
        self,
        module_name: str,
    ) -> PluginPolicyEntry | None:
        async with get_session() as session:
            result = await session.execute(
                select(PluginPolicyEntry).where(
                    PluginPolicyEntry.plugin_module == module_name
                )
            )
            return result.scalar_one_or_none()

    async def ensure_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str = "default_allow",
        required_level: int = 0,
        protection_mode: str = "normal",
    ) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(PluginPolicyEntry).where(
                    PluginPolicyEntry.plugin_module == module_name
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                session.add(
                    PluginPolicyEntry(
                        plugin_module=module_name,
                        access_mode=access_mode,
                        required_level=required_level,
                        protection_mode=protection_mode,
                    )
                )
            else:
                if (
                    record.access_mode == "default_allow"
                    and access_mode != "default_allow"
                ):
                    record.access_mode = access_mode
                if record.required_level == 0 and required_level > 0:
                    record.required_level = required_level
                if record.protection_mode == "normal" and protection_mode != "normal":
                    record.protection_mode = protection_mode
            await session.commit()

    async def update_plugin_policy(
        self,
        module_name: str,
        *,
        access_mode: str | None = None,
        required_level: int | None = None,
        protection_mode: str | None = None,
    ) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(PluginPolicyEntry).where(
                    PluginPolicyEntry.plugin_module == module_name
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = PluginPolicyEntry(plugin_module=module_name)
                session.add(record)
            if access_mode is not None:
                record.access_mode = access_mode
            if required_level is not None:
                record.required_level = required_level
            if protection_mode is not None:
                record.protection_mode = protection_mode
            await session.commit()


plugin_catalog_repository = PluginCatalogRepository()
