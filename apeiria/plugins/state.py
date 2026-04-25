"""Runtime plugin state helpers shared by startup and management flows."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


async def get_disabled_plugin_modules(
    module_names: Collection[str] | None = None,
) -> set[str]:
    """Return globally disabled plugin modules recorded in plugin_state."""
    from apeiria.plugins.repository import plugin_catalog_repository

    enabled_map = await plugin_catalog_repository.get_enabled_map()
    disabled = {module for module, enabled in enabled_map.items() if not enabled}
    if module_names:
        allowed_modules = set(module_names)
        return {module for module in disabled if module in allowed_modules}
    return disabled


def get_disabled_plugin_modules_sync(
    module_names: Collection[str] | None = None,
) -> set[str]:
    """Synchronous wrapper for startup-time plugin state checks."""
    return asyncio.run(get_disabled_plugin_modules(module_names))
