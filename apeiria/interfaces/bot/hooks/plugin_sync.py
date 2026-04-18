"""Plugin sync hook — sync loaded plugins to PluginInfo table on startup."""

from __future__ import annotations

import nonebot
from nonebot import get_driver
from nonebot.log import logger

from apeiria.app.runtime.diagnostics import runtime_diagnostic_recorder
from apeiria.app.runtime.handler_registry import handler_registry
from apeiria.infra.plugin_metadata.builders import (
    handler_descriptor_builder,
    plugin_descriptor_builder,
)
from apeiria.shared.i18n import t


@get_driver().on_startup
async def sync_plugins() -> None:
    """Iterate all loaded plugins, parse metadata, upsert into PluginInfo table."""
    from nonebot_plugin_orm import get_session
    from sqlalchemy import select

    from apeiria.infra.db.models.plugin_info import PluginInfo
    from apeiria.infra.db.models.plugin_policy import PluginPolicyEntry
    from apeiria.infra.runtime.plugin_policy import get_default_protection_mode

    plugins = nonebot.get_loaded_plugins()
    logger.info("{}", t("plugin_sync.syncing", count=len(plugins)))

    handler_registry.clear()
    async with get_session() as session:
        for plugin in plugins:
            descriptor = plugin_descriptor_builder.build(plugin)
            handler_registry.replace_for_plugin(
                descriptor.module_name,
                handler_descriptor_builder.build_for_plugin(plugin),
            )
            module_name = descriptor.module_name
            meta = plugin.metadata
            usage = meta.usage if meta else None

            result = await session.execute(
                select(PluginInfo).where(PluginInfo.module_name == module_name)
            )
            record = result.scalar_one_or_none()
            if record is not None:
                record.name = descriptor.name
                record.description = descriptor.description
                record.usage = usage
                record.plugin_type = descriptor.plugin_type
                record.is_ui_hidden = descriptor.is_ui_hidden
                record.admin_level = descriptor.admin_level
                record.author = descriptor.author
                record.version = descriptor.version
            else:
                session.add(
                    PluginInfo(
                        module_name=module_name,
                        name=descriptor.name,
                        description=descriptor.description,
                        usage=usage,
                        plugin_type=descriptor.plugin_type,
                        is_ui_hidden=descriptor.is_ui_hidden,
                        admin_level=descriptor.admin_level,
                        author=descriptor.author,
                        version=descriptor.version,
                    )
                )

            policy_result = await session.execute(
                select(PluginPolicyEntry).where(
                    PluginPolicyEntry.plugin_module == module_name
                )
            )
            policy_record = policy_result.scalar_one_or_none()
            protection_mode = get_default_protection_mode(module_name)
            if policy_record is None:
                session.add(
                    PluginPolicyEntry(
                        plugin_module=module_name,
                        access_mode="default_allow",
                        required_level=descriptor.admin_level,
                        protection_mode=protection_mode,
                    )
                )
            else:
                if policy_record.required_level == 0 and descriptor.admin_level > 0:
                    policy_record.required_level = descriptor.admin_level
                if (
                    policy_record.protection_mode == "normal"
                    and protection_mode != "normal"
                ):
                    policy_record.protection_mode = protection_mode

        await session.commit()

    runtime_diagnostic_recorder.record(
        "plugin.sync",
        source="bot.hooks.plugin_sync",
        message="plugin_sync_completed",
        data={
            "plugin_count": len(plugins),
            "handler_count": len(handler_registry),
        },
    )
    logger.info("{}", t("plugin_sync.complete", count=len(plugins)))
