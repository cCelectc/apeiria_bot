from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_htmlrender import render_template

if TYPE_CHECKING:
    from .config import HelpConfig
    from .models import HelpPluginItem

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _default_logo_data_uri() -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" '
        'viewBox="0 0 96 96"><defs><linearGradient id="g" x1="0" y1="0" '
        'x2="1" y2="1"><stop offset="0%" stop-color="#6fd0ff"/>'
        '<stop offset="100%" stop-color="#4a86ff"/></linearGradient></defs>'
        '<rect x="18" y="16" width="60" height="60" rx="20" fill="url(#g)"/>'
        '<rect x="30" y="31" width="36" height="8" rx="4" fill="#fff"/>'
        '<rect x="30" y="44" width="36" height="8" rx="4" fill="#fff"'
        ' opacity=".95"/>'
        '<rect x="30" y="57" width="24" height="8" rx="4" fill="#fff"'
        ' opacity=".9"/>'
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)


def _norm_color(color: str) -> str:
    s = color.strip()
    return s if s.startswith("#") and len(s) in {4, 7} else "#4e96f7"


def _resolve_title(config: HelpConfig, *, is_superuser: bool) -> str:
    base = config.title or "功能菜单"
    return f"{base} (主人)" if is_superuser else base


_CMD_PREVIEW_COUNT = 4


def _build_menu_data(
    plugins: list[HelpPluginItem],
    *,
    prefix: str,
    config: HelpConfig,
    is_superuser: bool,
) -> dict[str, object]:
    groups: list[dict[str, object]] = []

    app_plugins = [_plugin_card(p, prefix, config) for p in plugins if not p.is_builtin]
    if app_plugins:
        groups.append({"label": "功能", "plugins": app_plugins})

    builtin_plugins = [_plugin_card(p, prefix, config) for p in plugins if p.is_builtin]
    if is_superuser and builtin_plugins:
        groups.append({"label": "内置", "plugins": builtin_plugins})

    return {
        "title": _resolve_title(config, is_superuser=is_superuser),
        "subtitle": config.subtitle or f"发送 {prefix}help <插件名> 查看详情",
        "prefix": prefix,
        "plugin_total": len(plugins),
        "accent_color": _norm_color(config.accent_color),
        "header_logo": _default_logo_data_uri(),
        "groups": groups,
        "footer": "Apeiria",
    }


def _plugin_card(
    p: HelpPluginItem,
    prefix: str,
    config: HelpConfig,
) -> dict[str, object]:
    card: dict[str, object] = {
        "name": p.name,
        "description": p.description,
        "icon_url": p.icon_url,
        "cmd_count": p.command_count,
    }
    if config.expand_commands:
        card["commands"] = [
            {
                "name": c.name,
                "description": c.description,
                "admin_only": c.admin_only,
                "usage": c.usage or f"{prefix}{c.name}",
            }
            for c in p.commands
        ]
    else:
        preview = p.commands[:_CMD_PREVIEW_COUNT]
        card["command_preview"] = " ".join(c.name for c in preview)
    return card


def _build_detail_data(
    plugin: HelpPluginItem,
    *,
    prefix: str,
    config: HelpConfig,
) -> dict[str, object]:
    return {
        "plugin": {
            "name": plugin.name,
            "plugin_id": plugin.plugin_id,
            "description": plugin.description,
            "icon_url": plugin.icon_url,
        },
        "commands": [
            {
                "name": c.name,
                "description": c.description,
                "aliases": c.aliases,
                "usage": c.usage or f"{prefix}{c.name}",
                "admin_only": c.admin_only,
            }
            for c in plugin.commands
        ],
        "usage": plugin.usage,
        "command_count": plugin.command_count,
        "prefix": prefix,
        "accent_color": _norm_color(config.accent_color),
        "header_logo": _default_logo_data_uri(),
        "footer": "Apeiria",
    }


async def _do_render(template_name: str, data: dict[str, object]) -> bytes:
    base_url = f"file://{_TEMPLATES_DIR.resolve()}"
    return await render_template(
        str(_TEMPLATES_DIR),
        template_name=template_name,
        templates=data,
        pages={"viewport": {"width": 960, "height": 10}, "base_url": base_url},
        wait=0,
    )


async def render_menu(  # noqa: PLR0913
    plugins: list[HelpPluginItem],
    *,
    bot: Any,
    prefix: str,
    config: HelpConfig,
    is_superuser: bool,
    matcher: Any,
) -> None:
    data = _build_menu_data(
        plugins, prefix=prefix, config=config, is_superuser=is_superuser
    )

    if _is_console(bot):
        await matcher.finish(_format_menu_text(plugins, prefix=prefix, config=config))

    try:
        img = await _do_render("main_menu.html", data)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning("帮助菜单渲染失败，降级为文本")
        await matcher.finish(_format_menu_text(plugins, prefix=prefix, config=config))
    else:
        await UniMessage.image(raw=img).send()


async def render_detail(
    plugin: HelpPluginItem,
    *,
    bot: Any,
    prefix: str,
    config: HelpConfig,
    matcher: Any,
) -> None:
    data = _build_detail_data(plugin, prefix=prefix, config=config)

    if _is_console(bot):
        await matcher.finish(_format_detail_text(plugin, prefix=prefix))

    try:
        img = await _do_render("plugin_detail.html", data)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning("插件详情渲染失败，降级为文本")
        await matcher.finish(_format_detail_text(plugin, prefix=prefix))
    else:
        await UniMessage.image(raw=img).send()


def _is_console(bot: Any) -> bool:
    try:
        return bot.adapter.get_name() == "Console"
    except Exception:  # noqa: BLE001
        return False


def _format_menu_text(
    plugins: list[HelpPluginItem],
    *,
    prefix: str,
    config: HelpConfig,
) -> str:
    title = config.title or "功能菜单"
    lines = [title, config.subtitle or "", ""]
    expanded = config.expand_commands

    for p in plugins:
        lines.append(f"【{p.name}】 {p.description or '暂无描述'}")
        if expanded:
            for c in p.commands:
                mark = " [仅超管]" if c.admin_only else ""
                lines.append(f"  - {c.name}{mark} {c.description}")
        else:
            preview = " ".join(c.name for c in p.commands[:_CMD_PREVIEW_COUNT])
            lines.append(f"  命令: {preview or '无命令'}")
    lines.extend(["", f"发送 {prefix}help <插件名> 查看详细命令"])
    return "\n".join(lines)


def _format_detail_text(
    plugin: HelpPluginItem,
    *,
    prefix: str,
) -> str:
    lines = [
        f"【{plugin.name}】",
        f"描述: {plugin.description or '暂无描述'}",
        "",
        "命令列表:",
    ]
    for c in plugin.commands:
        mark = " [仅超管]" if c.admin_only else ""
        usage = c.usage or f"{prefix}{c.name}"
        lines.append(f"- {c.name}{mark}  {usage}")
        if c.description:
            lines.append(f"  {c.description}")
        if c.aliases:
            lines.append(f"  别名: {' '.join(c.aliases)}")
    if plugin.usage:
        lines.extend(["", "使用方法", plugin.usage])
    return "\n".join(lines)
