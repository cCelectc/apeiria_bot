"""Runtime plugin state helpers shared by startup and management flows."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


async def get_disabled_plugin_modules(
    module_names: Collection[str] | None = None,
) -> set[str]:
    """Return globally disabled plugin modules recorded in PluginInfo."""
    from nonebot_plugin_orm import get_session
    from sqlalchemy import select

    from apeiria.db.models.plugin_info import PluginInfo

    async with get_session() as session:
        statement = select(PluginInfo.module_name).where(
            PluginInfo.is_global_enabled.is_(False)
        )
        if module_names:
            statement = statement.where(PluginInfo.module_name.in_(tuple(module_names)))
        result = await session.execute(statement)
        rows = result.scalars().all()
    return set(rows)


def get_disabled_plugin_modules_sync(
    module_names: Collection[str] | None = None,
) -> set[str]:
    """Synchronous wrapper for startup-time plugin state checks."""
    return asyncio.run(get_disabled_plugin_modules(module_names))
