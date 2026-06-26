"""Plugin discovery — walk loaded NoneBot plugins and build base help models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot

from apeiria.builtin_plugins.help.utils import find_plugin_icon
from apeiria.plugins.metadata.api import PluginType
from apeiria.utils.plugin_introspection import (
    get_plugin_extra,
    get_plugin_name,
    get_plugin_source,
)

from .models import PluginHelpInfo

if TYPE_CHECKING:
    from .config import HelpConfig


def _discover_plugins(
    config: HelpConfig,
    *,
    role: str,
    show_all: bool,
) -> dict[str, PluginHelpInfo]:
    """Discover loaded plugins and build the base help model."""
    blacklist = set(config.plugin_blacklist) if not show_all else set()
    result: dict[str, PluginHelpInfo] = {}

    for plugin in nonebot.get_loaded_plugins():
        meta = plugin.metadata
        if not meta:
            continue

        extra = get_plugin_extra(plugin)
        if extra and extra.ui.hidden:
            continue
        if extra and not _plugin_visible_in_role(
            extra.plugin_type,
            role,
        ):
            continue

        source = get_plugin_source(plugin)
        if not config.show_builtin_cmds and source in {"builtin", "framework"}:
            continue
        if plugin.id_ in blacklist or plugin.module_name in blacklist:
            continue

        module_file = getattr(getattr(plugin, "module", None), "__file__", None)
        icon_url = find_plugin_icon(module_file, seed=plugin.module_name)
        result[plugin.id_] = PluginHelpInfo(
            plugin_id=plugin.id_,
            module_name=plugin.module_name,
            name=get_plugin_name(plugin),
            display_name=get_plugin_name(plugin),
            description=meta.description or "",
            usage=meta.usage or "",
            plugin_type=extra.plugin_type.value if extra else "normal",
            version=extra.version if extra else "",
            source=source,
            icon_url=icon_url,
            menu_category=extra.menu_category.strip() if extra else "",
            introduction=extra.introduction.strip() if extra else "",
            precautions=[item.strip() for item in extra.precautions] if extra else [],
            owner_help=extra.owner_help.strip() if extra else "",
        )

    return result


def _plugin_visible_in_role(
    plugin_type: PluginType,
    role: str,
) -> bool:
    if role == "owner":
        return True
    if role == "admin":
        return plugin_type == PluginType.NORMAL
    return plugin_type == PluginType.NORMAL


def _get_loaded_plugin(plugin_id: str):
    for plugin in nonebot.get_loaded_plugins():
        if plugin.id_ == plugin_id:
            return plugin
    return None
