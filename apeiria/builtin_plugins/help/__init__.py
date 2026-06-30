"""Help plugin — auto-generated command help system (v2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import require
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

from .commands import _cmd_prefix
from .config import HelpConfig, get_help_config
from .renderer import (
    _show_detail,
    _show_menu,
)

if TYPE_CHECKING:
    from .models import HelpViewRole

# ── help command ───────────────────────────────────────────────────────────

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


async def _resolve_role(
    bot: Bot,
    event: Event,
    *,
    config: HelpConfig,
    force_admin: bool,
    force_owner: bool,
) -> HelpViewRole:
    is_owner = await SUPERUSER(bot, event)

    if force_owner:
        if not is_owner:
            await _help.finish("仅机器人主人可使用此选项")
        return "owner"
    if force_admin:
        if not is_owner:
            await _help.finish("仅机器人主人可切换到管理员视图")
        return "admin"
    if not config.enable_role_views or config.role_view_mode == "manual_only":
        return "owner" if is_owner and config.admin_show_all else "user"
    return "owner" if is_owner else "user"


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
    role = await _resolve_role(
        bot,
        event,
        config=config,
        force_admin=show_admin_flag.available,
        force_owner=show_all_flag.available,
    )
    show_all = (
        role == "owner"
        and await SUPERUSER(bot, event)
        and (config.admin_show_all or show_all_flag.available)
    )
    target_name = _merge_plugin_name(plugin_name)

    if target_name:
        await _show_detail(
            bot,
            target_name,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
            matcher=_help,
        )
    else:
        await _show_menu(
            bot,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
            matcher=_help,
        )


def _merge_plugin_name(m: Match[tuple[str, ...]]) -> str | None:
    if not m.available:
        return None
    parts = [
        item.strip() for item in m.result if isinstance(item, str) and item.strip()
    ]
    return " ".join(parts) if parts else None


# ── plugin metadata ────────────────────────────────────────────────────────

__plugin_meta__ = PluginMetadata(
    name="命令帮助",
    description="自动生成命令帮助菜单，支持角色区分和图片渲染",
    usage="发送 /help 查看功能菜单",
    type="application",
    config=HelpConfig,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)
