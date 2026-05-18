"""Plugin sync hook - ensure loaded plugins have governance state."""

from __future__ import annotations

import nonebot
from nonebot.log import logger

from apeiria.i18n import t
from apeiria.plugins.metadata.builders import plugin_descriptor_builder


async def sync_plugins() -> None:
    """Iterate loaded plugins and ensure a SQLite governance row exists."""
    from apeiria.plugins.protection import get_default_protection_mode
    from apeiria.plugins.repository import plugin_catalog_repository

    plugins = nonebot.get_loaded_plugins()
    logger.info("{}", t("plugin_sync.syncing", count=len(plugins)))

    for plugin in plugins:
        descriptor = plugin_descriptor_builder.build(plugin)
        module_name = descriptor.module_name
        await plugin_catalog_repository.ensure_plugin_policy(
            module_name,
            protection_mode=get_default_protection_mode(module_name),
        )

    logger.info("{}", t("plugin_sync.complete", count=len(plugins)))
