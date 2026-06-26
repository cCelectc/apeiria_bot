from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from nonebot.log import logger
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_htmlrender import render_template

from .commands import _display_name
from .generator import find_plugin_by_name, generate_help_list

if TYPE_CHECKING:
    from .config import HelpConfig
    from .models import HelpViewRole, PluginHelpInfo

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_FULL_CMD_COUNT = 4


def _resolve_data_uri(path_str: str) -> str:
    stripped = path_str.strip()
    if not stripped:
        return ""
    path = Path(stripped).resolve()
    if not path.is_file():
        return ""
    mime, _ = mimetypes.guess_type(str(path))
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime or 'image/png'};base64,{encoded}"


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


def _resolve_logo(config: HelpConfig) -> str:
    return _resolve_data_uri(config.header_logo) or _default_logo_data_uri()


def _resolve_banner(config: HelpConfig) -> str:
    return _resolve_data_uri(config.banner_image)


def _norm_color(color: str) -> str:
    s = color.strip()
    return s if s.startswith("#") and len(s) in {4, 7} else "#4e96f7"


def _resolve_title(config: HelpConfig, role: HelpViewRole) -> str:
    default = "功能菜单"
    if role == "owner":
        return (config.owner_title or config.title or default).strip()
    if role == "admin":
        return (config.admin_title or config.title or default).strip()
    return (config.user_title or config.title or default).strip()


def _resolve_view_label(role: HelpViewRole) -> str:
    return {"owner": "主人视图", "admin": "管理员视图"}.get(role, "用户视图")


def _footer_text(config: HelpConfig) -> str:
    return config.footer_text.strip() or "Apeiria"


def _build_menu_data(
    plugins: list[PluginHelpInfo],
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
) -> dict[str, object]:
    if config.expand_commands:
        entries = [
            {
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "icon_url": p.icon_url,
                "cmd_count": p.command_count,
                "menu_category": p.menu_category,
                "commands": [
                    {
                        "display_name": _display_name(prefix, c.name, c.custom_prefix),
                        "description": c.description,
                        "admin_only": c.admin_only,
                    }
                    for c in p.commands
                ],
            }
            for p in plugins
        ]
    else:
        entries = [
            {
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "icon_url": p.icon_url,
                "cmd_count": p.command_count,
                "menu_category": p.menu_category,
            }
            for p in plugins
        ]

    return {
        "title": _resolve_title(config, role),
        "subtitle": config.subtitle or f"发送 {prefix}help <插件名> 查看详情",
        "view_label": _resolve_view_label(role),
        "prefix": prefix,
        "plugin_total": len(plugins),
        "accent_color": _norm_color(config.accent_color),
        "banner_image": _resolve_banner(config),
        "header_logo": _resolve_logo(config),
        "font_urls": [u for u in config.font_urls if u],
        "font_family": config.font_family.strip(),
        "latin_font_family": config.latin_font_family.strip(),
        "mono_font_family": config.mono_font_family.strip(),
        "plugins": entries,
        "footer": _footer_text(config),
    }


def _build_detail_data(
    plugin: PluginHelpInfo,
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
) -> dict[str, object]:
    return {
        "plugin": {
            "name": plugin.name,
            "plugin_id": plugin.plugin_id,
            "module_name": plugin.module_name,
            "display_name": plugin.display_name,
            "description": plugin.description,
            "icon_url": plugin.icon_url,
            "menu_category": plugin.menu_category,
            "introduction": plugin.introduction or plugin.description,
            "precautions": plugin.precautions,
            "owner_help": plugin.owner_help if role == "owner" else "",
            "view_label": _resolve_view_label(role),
        },
        "commands": [
            {
                "display_name": _display_name(prefix, c.name, c.custom_prefix),
                "description": c.description,
                "aliases": [
                    _display_name(prefix, a, c.custom_prefix) for a in c.aliases
                ],
                "usage": c.usage,
                "admin_only": c.admin_only,
            }
            for c in plugin.commands
        ],
        "command_count": len(plugin.commands),
        "prefix": prefix,
        "accent_color": _norm_color(config.accent_color),
        "font_urls": [u for u in config.font_urls if u],
        "font_family": config.font_family.strip(),
        "latin_font_family": config.latin_font_family.strip(),
        "mono_font_family": config.mono_font_family.strip(),
        "footer": _footer_text(config),
        "labels": {
            "introduction": "功能简介",
            "precautions": "注意事项",
            "owner_help": "维护者帮助",
        },
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


async def _show_menu(  # noqa: PLR0913
    bot: Any,
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
    show_all: bool,
    matcher: Any,
) -> None:
    plugins = generate_help_list(config, role=role, show_all=show_all)
    tpl = "expanded_menu.html" if config.expand_commands else "main_menu.html"
    data = _build_menu_data(plugins, prefix=prefix, config=config, role=role)

    if bot.adapter.get_name() == "Console":
        await matcher.finish(
            _format_menu_text(plugins, prefix=prefix, config=config, role=role)
        )

    try:
        img = await _do_render(tpl, data)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning("帮助菜单渲染失败，降级为文本")
        await matcher.finish(
            _format_menu_text(plugins, prefix=prefix, config=config, role=role)
        )
    else:
        await UniMessage.image(raw=img).send()


async def _show_detail(  # noqa: PLR0913
    bot: Any,
    name: str,
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
    show_all: bool,
    matcher: Any,
) -> None:
    info = find_plugin_by_name(name, config, role=role, show_all=show_all)
    if not info:
        await matcher.finish(f"未找到插件「{name}」")
    assert info is not None
    data = _build_detail_data(info, prefix=prefix, config=config, role=role)

    if bot.adapter.get_name() == "Console":
        await matcher.finish(_format_detail_text(info, prefix=prefix, role=role))

    try:
        img = await _do_render("sub_menu.html", data)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning("插件详情渲染失败，降级为文本")
        await matcher.finish(_format_detail_text(info, prefix=prefix, role=role))
    else:
        await UniMessage.image(raw=img).send()


def _format_menu_text(
    plugins: list[PluginHelpInfo],
    *,
    prefix: str,
    config: HelpConfig,
    role: HelpViewRole,
) -> str:
    expanded = config.expand_commands
    lines = ["命令帮助菜单", f"视图: {_resolve_view_label(role)}", ""]
    for p in plugins:
        lines.append(f"【{p.display_name}】 {p.description or '暂无描述'}")
        if p.menu_category:
            lines.append(f"  分类: {p.menu_category}")
        if expanded:
            lines.extend(
                f"  - {_display_name(prefix, c.name, c.custom_prefix)}"
                for c in p.commands
            )
        else:
            preview = " ".join(
                _display_name(prefix, c.name, c.custom_prefix)
                for c in p.commands[:_FULL_CMD_COUNT]
            )
            lines.append(f"  命令: {preview or '无命令'}")
    lines.extend(["", f"发送 {prefix}help <插件名> 查看详细命令"])
    return "\n".join(lines)


def _format_detail_text(
    info: PluginHelpInfo,
    *,
    prefix: str,
    role: HelpViewRole,
) -> str:
    lines = [
        f"【{info.display_name}】 v{info.version or 'unknown'}",
        f"视图: {_resolve_view_label(role)}",
        f"类型: {info.plugin_type}",
        f"来源: {info.source}",
        f"描述: {info.description or '暂无描述'}",
        "",
        "命令列表:",
    ]
    if info.menu_category:
        lines.insert(5, f"分类: {info.menu_category}")
    if info.introduction:
        lines.extend(["", "功能介绍", info.introduction])

    for c in info.commands:
        dn = _display_name(prefix, c.name, c.custom_prefix)
        lines.append(f"- {dn}")
        if c.description:
            lines.append(f"  {c.description}")
        if c.aliases:
            aliases = " ".join(
                _display_name(prefix, a, c.custom_prefix) for a in c.aliases
            )
            lines.append(f"  别名: {aliases}")
        if c.usage:
            lines.append(f"  {c.usage}")

    if info.usage:
        lines.extend(["", "使用方法", info.usage])
    if info.precautions:
        lines.append("")
        lines.append("注意事项")
        lines.extend(f"- {item}" for item in info.precautions)
    if role == "owner" and info.owner_help:
        lines.extend(["", "维护者帮助", info.owner_help])
    return "\n".join(lines)
