"""Plugin sync hook — sync loaded plugins to PluginInfo table on startup."""

from __future__ import annotations

import nonebot
from nonebot import get_driver
from nonebot.log import logger

from apeiria.shared.i18n import t
from apeiria.shared.plugin_metadata import PluginExtraData


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

    async with get_session() as session:
        for plugin in plugins:
            module_name = plugin.module_name
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
            description = meta.description if meta else None
            usage = meta.usage if meta else None
            plugin_type = extra.plugin_type.value if extra else "normal"
            admin_level = extra.admin_level if extra else 0
            author = extra.author if extra else None
            version = extra.version if extra else None

            result = await session.execute(
                select(PluginInfo).where(PluginInfo.module_name == module_name)
            )
            record = result.scalar_one_or_none()
            if record is not None:
                record.name = name
                record.description = description
                record.usage = usage
                record.plugin_type = plugin_type
                record.admin_level = admin_level
                record.author = author
                record.version = version
            else:
                session.add(
                    PluginInfo(
                        module_name=module_name,
                        name=name,
                        description=description,
                        usage=usage,
                        plugin_type=plugin_type,
                        admin_level=admin_level,
                        author=author,
                        version=version,
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
                        required_level=admin_level,
                        protection_mode=protection_mode,
                    )
                )
            else:
                if policy_record.required_level == 0 and admin_level > 0:
                    policy_record.required_level = admin_level
                if (
                    policy_record.protection_mode == "normal"
                    and protection_mode != "normal"
                ):
                    policy_record.protection_mode = protection_mode

        await session.commit()

    logger.info("{}", t("plugin_sync.complete", count=len(plugins)))
