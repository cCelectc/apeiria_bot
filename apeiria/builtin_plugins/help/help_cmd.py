"""Help command handler."""

from collections.abc import Sequence

import nonebot
from arclet.alconna import Args, CommandMeta, MultiVar, Option
from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot_plugin_alconna import Alconna, Match, on_alconna
from nonebot_plugin_alconna.uniseg import UniMessage

from apeiria.builtin_plugins.help.config import HelpConfig, get_help_config
from apeiria.builtin_plugins.help.generator import (
    HelpViewRole,
    PluginHelpInfo,
    find_plugin_by_name,
    generate_help_list,
)
from apeiria.i18n import t
from apeiria.utils.command_prefix import get_command_prefix

_help = on_alconna(
    Alconna(
        "help",
        Args["plugin_name?", MultiVar(str, "*")],
        Option("--admin"),
        Option("--all"),
        meta=CommandMeta(description=t("help.command.help")),
    ),
    aliases={"帮助", "菜单", "功能"},
    use_cmd_start=True,
    priority=1,
    block=True,
)


def _is_console(bot: Bot) -> bool:
    return bot.adapter.get_name() == "Console"


def _is_superuser(event: Event) -> bool:
    user_id = event.get_user_id()
    superusers = getattr(nonebot.get_driver().config, "superusers", set())
    return str(user_id) in {str(item) for item in superusers}


async def _resolve_help_role(
    _bot: Bot,
    event: Event,
    *,
    config: HelpConfig,
    force_admin: bool,
    force_owner: bool,
) -> HelpViewRole:
    is_owner = _is_superuser(event)

    if force_owner:
        if not is_owner:
            await _help.finish(t("help.owner_forbidden"))
        return "owner"
    if force_admin:
        if not is_owner:
            await _help.finish(t("help.admin_forbidden"))
        return "admin"
    if not config.enable_role_views or config.role_view_mode == "manual_only":
        return "owner" if is_owner and config.admin_show_all else "user"
    if is_owner:
        return "owner"
    return "user"


def _format_help_list_text(
    plugins: Sequence[PluginHelpInfo],
    *,
    prefix: str,
    expanded: bool,
    role: HelpViewRole,
) -> str:
    lines = [t("help.list_title"), t(f"help.view_{role}"), ""]
    for plugin in plugins:
        lines.append(
            f"【{plugin.display_name}】 "
            f"{plugin.description or t('help.no_description')}"
        )
        if plugin.menu_category:
            lines.append(f"  {t('help.detail_category')}: {plugin.menu_category}")
        if expanded:
            lines.extend(
                [
                    f"  - {_display_name(prefix, command.name, command.custom_prefix)}"
                    for command in plugin.commands
                ]
            )
        else:
            preview = " ".join(
                _display_name(prefix, command.name, command.custom_prefix)
                for command in plugin.commands[:4]
            )
            command_text = preview or t("help.no_commands")
            lines.append(f"  {t('help.commands_label')}: {command_text}")

    lines.append("")
    lines.append(t("help.list_footer"))
    return "\n".join(lines)


def _format_plugin_detail_text(  # noqa: C901
    plugin_info: PluginHelpInfo,
    *,
    prefix: str,
    role: HelpViewRole,
) -> str:
    lines = [
        f"【{plugin_info.display_name}】 v{plugin_info.version or 'unknown'}",
        f"{t('help.detail_view')}: {t(f'help.view_{role}')}",
        f"{t('help.detail_type')}: {plugin_info.plugin_type}",
        f"{t('help.detail_source')}: {plugin_info.source}",
        f"{t('help.detail_description')}: "
        f"{plugin_info.description or t('help.no_description')}",
        "",
        t("help.commands_label") + ":",
    ]
    if plugin_info.menu_category:
        lines.insert(5, f"{t('help.detail_category')}: {plugin_info.menu_category}")
    if plugin_info.introduction:
        lines.extend(["", t("help.detail_introduction"), plugin_info.introduction])

    if not plugin_info.commands:
        lines.append(f"- {t('help.no_commands')}")

    for command in plugin_info.commands:
        display_name = _display_name(prefix, command.name, command.custom_prefix)
        lines.append(f"- {display_name}")
        if command.description:
            lines.append(f"  {command.description}")
        if command.aliases:
            aliases = " ".join(
                _display_name(prefix, alias, command.custom_prefix)
                for alias in command.aliases
            )
            lines.append(f"  {t('help.aliases_label')}: {aliases}")
        if command.usage:
            lines.append(f"  {command.usage}")

    if plugin_info.usage:
        lines.extend(["", t("help.detail_usage"), plugin_info.usage])
    if plugin_info.precautions:
        lines.extend(["", t("help.detail_precautions")])
        lines.extend(f"- {item}" for item in plugin_info.precautions)
    if role == "owner" and plugin_info.owner_help:
        lines.extend(["", t("help.detail_owner_help"), plugin_info.owner_help])
    return "\n".join(lines)


@_help.handle()
async def handle_help(
    bot: Bot,
    event: Event,
    plugin_name: Match[tuple[str, ...]],
    show_admin_flag: Match[object],
    show_all_flag: Match[object],
) -> None:
    config = get_help_config()
    prefix = get_command_prefix()
    role = await _resolve_help_role(
        bot,
        event,
        config=config,
        force_admin=show_admin_flag.available,
        force_owner=show_all_flag.available,
    )
    show_all = (
        role == "owner"
        and _is_superuser(event)
        and (config.admin_show_all or show_all_flag.available)
    )
    target_name = _merge_plugin_name(plugin_name)

    if target_name:
        await _show_plugin_detail(
            bot,
            target_name,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
        )
    else:
        await _show_help_list(
            bot,
            prefix=prefix,
            config=config,
            role=role,
            show_all=show_all,
        )


async def _show_help_list(
    bot: Bot,
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
    show_all: bool,
) -> None:
    plugins = generate_help_list(config, role=role, show_all=show_all)

    if _is_console(bot):
        await _help.finish(
            _format_help_list_text(
                plugins,
                prefix=prefix,
                expanded=config.expand_commands,
                role=role,
            )
        )

    from .renderer import render_help_menu

    try:
        img_bytes = await render_help_menu(
            plugins,
            prefix=prefix,
            config=config,
            role=role,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning(
            "Help menu image render failed, fallback to text."
        )
        await _help.finish(
            _format_help_list_text(
                plugins,
                prefix=prefix,
                expanded=config.expand_commands,
                role=role,
            )
        )

    await UniMessage.image(raw=img_bytes).send()


async def _show_plugin_detail(  # noqa: PLR0913
    bot: Bot,
    name: str,
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
    show_all: bool,
) -> None:
    plugin_info = find_plugin_by_name(name, config, role=role, show_all=show_all)
    if not plugin_info:
        await _help.finish(t("help.not_found", name=name))

    if _is_console(bot):
        await _help.finish(
            _format_plugin_detail_text(plugin_info, prefix=prefix, role=role)
        )

    from .renderer import render_plugin_detail

    try:
        img_bytes = await render_plugin_detail(
            plugin_info,
            prefix=prefix,
            config=config,
            role=role,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning(
            "Help detail image render failed, fallback to text."
        )
        await _help.finish(
            _format_plugin_detail_text(plugin_info, prefix=prefix, role=role)
        )

    await UniMessage.image(raw=img_bytes).send()


def _display_name(prefix: str, name: str, custom_prefix: str | None) -> str:
    effective_prefix = prefix if custom_prefix is None else custom_prefix
    return f"{effective_prefix}{name}"


def _merge_plugin_name(plugin_name: Match[tuple[str, ...]]) -> str | None:
    parts = (
        [
            item.strip()
            for item in plugin_name.result
            if isinstance(item, str) and item.strip()
        ]
        if plugin_name.available
        else []
    )
    if not parts:
        return None
    return " ".join(parts)
