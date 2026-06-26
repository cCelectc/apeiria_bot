from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nonebot

from apeiria.plugin.metadata.api import (
    CommandDeclaration,
    PluginExtraData,
    PluginType,
)

from .commands import _cmd_sort_key, _collect_matcher_commands
from .models import CommandHelpInfo, PluginHelpInfo

if TYPE_CHECKING:
    from .config import HelpConfig, PluginOverride
    from .models import HelpViewRole

_THIRD_PARTY_PREFIXES = ("nonebot_plugin_", "nonebot.")


def _get_extra(plugin: Any) -> PluginExtraData | None:
    if plugin.metadata and plugin.metadata.extra:
        return PluginExtraData.from_extra(plugin.metadata.extra)
    return None


def _plugin_source(plugin: Any) -> str:
    mf = getattr(getattr(plugin, "module", None), "__file__", None) or ""
    mn = plugin.module_name or ""
    if "builtin_plugins" in mf or mn.startswith("apeiria.builtin_plugins"):
        return "builtin"
    if mn.startswith("apeiria."):
        return "framework"
    if mn.startswith(_THIRD_PARTY_PREFIXES):
        return "third_party"
    return "user"


def _find_icon(module_file: str | None) -> str:
    if module_file:
        base = Path(module_file).resolve().parent
        for ext in ("png", "webp", "jpg", "jpeg", "svg"):
            p = base / f"logo.{ext}"
            if p.is_file():
                mime = f"image/{'svg+xml' if ext == 'svg' else ext}"
                data = p.read_bytes()
                return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    return "https://nonebot.dev/logo.png"


def _plugin_sort_key(p: PluginHelpInfo) -> tuple[int, int, str]:
    return (p.order, 0 if p.is_builtin else 1, p.display_name.lower())


def _discover_plugins(
    config: HelpConfig,
    *,
    role: str,
    show_all: bool,
) -> dict[str, PluginHelpInfo]:
    blacklist = set(config.plugin_blacklist) if not show_all else set()
    result: dict[str, PluginHelpInfo] = {}

    for plugin in nonebot.get_loaded_plugins():
        meta = plugin.metadata
        if not meta:
            continue

        extra = _get_extra(plugin)
        if extra and extra.ui.hidden:
            continue
        if extra and role != "owner" and extra.plugin_type == PluginType.SUPERUSER:
            continue

        source = _plugin_source(plugin)
        if not config.show_builtin_cmds and source in {"builtin", "framework"}:
            continue
        if plugin.id_ in blacklist or plugin.module_name in blacklist:
            continue

        module_file = getattr(getattr(plugin, "module", None), "__file__", None)
        icon_url = _find_icon(module_file)

        result[plugin.id_] = PluginHelpInfo(
            plugin_id=plugin.id_,
            module_name=plugin.module_name,
            name=meta.name or plugin.module_name,
            display_name=meta.name or plugin.module_name,
            description=meta.description or "",
            usage=meta.usage or "",
            plugin_type=extra.plugin_type.value if extra else "normal",
            version=extra.version if extra else "",
            source=source,
            icon_url=icon_url,
            menu_category=(extra.help.category.strip() if extra else ""),
            introduction=(extra.help.introduction.strip() if extra else ""),
            precautions=([s.strip() for s in extra.help.precautions] if extra else []),
            owner_help=(extra.help.owner_help.strip() if extra else ""),
        )
    return result


def _merge_declared_commands(
    existing: list[CommandHelpInfo],
    declared: list[str | CommandDeclaration],
) -> list[CommandHelpInfo]:
    merged: dict[str, CommandHelpInfo] = {c.name: c for c in existing}
    for item in declared:
        if isinstance(item, str):
            name = item.strip()
            if not name or name in merged:
                continue
            merged[name] = CommandHelpInfo(name=name)
        elif isinstance(item, CommandDeclaration):
            name = item.name.strip()
            if not name:
                continue
            cur = merged.get(name)
            aliases = sorted(
                a.strip()
                for a in item.aliases
                if isinstance(a, str) and a.strip() and a.strip() != name
            )
            if cur is None:
                merged[name] = CommandHelpInfo(
                    name=name,
                    description=item.description.strip(),
                    aliases=aliases,
                    usage=item.usage.strip(),
                    custom_prefix=item.custom_prefix,
                )
            else:
                merged[name] = _merge_cmd_info(cur, item, aliases)
    return list(merged.values())


def _merge_cmd_info(
    cur: CommandHelpInfo,
    item: CommandDeclaration,
    aliases: list[str],
) -> CommandHelpInfo:
    return CommandHelpInfo(
        name=cur.name,
        description=cur.description or item.description.strip(),
        aliases=sorted(set(cur.aliases) | set(aliases)),
        usage=cur.usage or item.usage.strip(),
        admin_only=cur.admin_only,
        custom_prefix=(
            cur.custom_prefix if cur.custom_prefix is not None else item.custom_prefix
        ),
    )


def _parse_pipe_command(raw: str) -> CommandHelpInfo | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    parts = [p.strip() for p in raw.split("|")]
    if not parts[0]:
        return None
    return CommandHelpInfo(
        name=parts[0],
        description=parts[1] if len(parts) > 1 else "",
        custom_prefix=parts[2] if len(parts) > 2 else None,  # noqa: PLR2004
    )


def _apply_overrides(
    plugins: list[PluginHelpInfo],
    overrides: list[PluginOverride],
) -> None:
    pmap: dict[str, PluginHelpInfo] = {}
    for p in plugins:
        pmap[p.plugin_id] = p
        pmap[p.name] = p
        pmap[p.module_name] = p

    for ov in overrides:
        target = pmap.get(ov.plugin_name)
        if target is None:
            mn = f"override.{ov.plugin_name or 'plugin'}"
            target = PluginHelpInfo(
                plugin_id=mn,
                module_name=mn,
                name=ov.plugin_name or "未命名插件",
                display_name=ov.plugin_name or "未命名插件",
                source="custom",
                icon_url=_find_icon(None),
                order=ov.order,
            )
            plugins.append(target)
            pmap[target.plugin_id] = target
            pmap[target.name] = target
            pmap[target.module_name] = target

        if ov.display_name:
            target.display_name = ov.display_name
        if ov.description:
            target.description = ov.description
        if ov.category:
            target.menu_category = ov.category
        target.order = ov.order

        for raw in ov.extra_commands:
            cmd = _parse_pipe_command(raw)
            if cmd is None:
                continue
            target.commands = [c for c in target.commands if c.name != cmd.name]
            target.commands.append(cmd)


def _normalize_cmd_aliases(cmd: CommandHelpInfo) -> CommandHelpInfo:
    return CommandHelpInfo(
        name=cmd.name,
        description=cmd.description.strip(),
        aliases=sorted(
            {
                a.strip()
                for a in cmd.aliases
                if isinstance(a, str) and a.strip() and a.strip() != cmd.name
            }
        ),
        usage=cmd.usage.strip(),
        admin_only=cmd.admin_only,
        custom_prefix=cmd.custom_prefix,
    )


def _dedupe_and_normalize_commands(
    cmds: list[CommandHelpInfo],
) -> list[CommandHelpInfo]:
    seen: dict[str, CommandHelpInfo] = {}
    for c in cmds:
        e = seen.get(c.name)
        if e is None:
            seen[c.name] = c
            continue
        seen[c.name] = CommandHelpInfo(
            name=e.name,
            description=e.description or c.description,
            aliases=sorted(set(e.aliases) | set(c.aliases)),
            usage=e.usage or c.usage,
            admin_only=e.admin_only or c.admin_only,
            custom_prefix=(
                e.custom_prefix if e.custom_prefix is not None else c.custom_prefix
            ),
        )
    return [seen[key] for key in sorted(seen)]


def generate_help_list(
    config: HelpConfig,
    *,
    role: HelpViewRole = "user",
    show_all: bool = False,
) -> list[PluginHelpInfo]:
    plugins = _discover_plugins(config, role=role, show_all=show_all)
    cmd_index = _collect_matcher_commands(plugins)

    result: list[PluginHelpInfo] = []
    for plugin in plugins.values():
        commands = cmd_index.get(plugin.plugin_id, [])
        loaded = _find_loaded_plugin(plugin.plugin_id)
        extra = _get_extra(loaded) if loaded else None
        if extra:
            commands = _merge_declared_commands(commands, extra.commands)
        plugin.commands = sorted(commands, key=_cmd_sort_key)
        result.append(plugin)

    _apply_overrides(result, config.plugin_overrides)
    for p in result:
        p.commands = _dedupe_and_normalize_commands(p.commands)
        p.commands = [_normalize_cmd_aliases(c) for c in p.commands]

    result = [p for p in result if p.commands]
    result.sort(key=_plugin_sort_key)
    return result


def _find_loaded_plugin(plugin_id: str) -> Any:
    for p in nonebot.get_loaded_plugins():
        if p.id_ == plugin_id:
            return p
    return None


def find_plugin_by_name(
    name: str,
    config: HelpConfig,
    *,
    role: HelpViewRole = "user",
    show_all: bool = False,
) -> PluginHelpInfo | None:
    all_plugins = generate_help_list(config, role=role, show_all=show_all)
    nl = name.lower()
    for p in all_plugins:
        candidates = (
            p.display_name.lower(),
            p.name.lower(),
            p.module_name.lower(),
            p.plugin_id.lower(),
        )
        if nl in candidates:
            return p
    for p in all_plugins:
        lower_vals = (
            p.display_name.lower(),
            p.name.lower(),
            p.module_name.lower(),
        )
        if any(nl in v for v in lower_vals):
            return p
    return None
