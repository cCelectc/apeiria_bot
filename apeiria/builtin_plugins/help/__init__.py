"""Help plugin — metadata-driven command help system."""

from __future__ import annotations

from nonebot import get_driver, require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Match,
    MultiVar,
    Option,
    on_alconna,
)

require("nonebot_plugin_htmlrender")

from .config import HelpConfig, get_help_config
from .probe import discover_plugins, find_plugin_by_name
from .renderer import render_detail, render_menu

_help = on_alconna(
    Alconna(
        "help",
        Args["plugin_name?", MultiVar(str, "*")],
        Option("--admin", dest="show_admin_flag"),
        Option("--all", dest="show_all_flag"),
        meta=CommandMeta(description="查看功能菜单"),
    ),
    aliases={"帮助", "菜单", "功能"},
    use_cmd_start=True,
    priority=1,
    block=True,
)


@_help.handle()
async def _handle_help(
    bot: Bot,
    event: Event,
    plugin_name: Match[tuple[str, ...]],
    show_admin_flag: Match[object],
    show_all_flag: Match[object],
) -> None:
    config = get_help_config()
    prefix = _cmd_prefix()
    is_owner = await SUPERUSER(bot, event)
    has_flag = show_admin_flag.available or show_all_flag.available

    if has_flag and not is_owner:
        await _help.finish("仅主人可切换视图")

    is_superuser = is_owner or has_flag
    show_all = has_flag

    target_name = _merge_plugin_name(plugin_name)

    if target_name:
        plugin = find_plugin_by_name(
            target_name, config, is_superuser=is_superuser, show_all=show_all
        )
        if not plugin:
            await _help.finish(f"未找到插件「{target_name}」")
        await render_detail(
            plugin, bot=bot, prefix=prefix, config=config, matcher=_help
        )
    else:
        plugins = discover_plugins(config, is_superuser=is_superuser, show_all=show_all)
        await render_menu(
            plugins,
            bot=bot,
            prefix=prefix,
            config=config,
            is_superuser=is_superuser,
            matcher=_help,
        )


def _cmd_prefix() -> str:
    prefixes = get_driver().config.command_start
    return next(iter(prefixes)) if prefixes else "/"


def _merge_plugin_name(m: Match[tuple[str, ...]]) -> str | None:
    if not m.available:
        return None
    parts = [
        item.strip() for item in m.result if isinstance(item, str) and item.strip()
    ]
    return " ".join(parts) if parts else None


__plugin_meta__ = PluginMetadata(
    name="命令帮助",
    description="查看与搜索所有已加载插件的命令与用法",
    usage="发送 /help 查看功能菜单；/help <插件名> 查看插件详情",
    type="application",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    config=HelpConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)
