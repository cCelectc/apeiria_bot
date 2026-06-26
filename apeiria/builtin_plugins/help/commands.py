from __future__ import annotations

from typing import Any

from nonebot import get_driver
from nonebot.matcher import matchers
from nonebot.rule import CommandRule

from .models import CommandHelpInfo, PluginHelpInfo


def _cmd_prefix() -> str:
    prefixes = get_driver().config.command_start
    return next(iter(prefixes)) if prefixes else "/"


def _display_name(prefix: str, name: str, custom_prefix: str | None) -> str:
    return f"{custom_prefix or prefix}{name}"


def _cmd_sort_key(cmd: CommandHelpInfo) -> str:
    return cmd.name


def _collect_matcher_commands(
    plugins: dict[str, PluginHelpInfo],
) -> dict[str, list[CommandHelpInfo]]:
    out: dict[str, dict[str, CommandHelpInfo]] = {}

    for mgroup in matchers.values():
        for matcher in mgroup:
            plugin_id = getattr(matcher, "plugin_name", None)
            if not plugin_id or plugin_id not in plugins:
                continue
            cmd = _extract_matcher_command(matcher, plugins[plugin_id])
            if cmd is None:
                continue
            out.setdefault(plugin_id, {})[cmd.name] = cmd

    return {pid: sorted(m.values(), key=_cmd_sort_key) for pid, m in out.items()}


def _extract_matcher_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    cmd = _extract_alconna_command(matcher, plugin)
    return cmd if cmd is not None else _extract_standard_command(matcher, plugin)


def _extract_alconna_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    cpath = getattr(matcher, "_command_path", "")
    factory = getattr(matcher, "command", None)
    if not cpath or not callable(factory):
        return None
    try:
        ac = factory()
    except Exception:  # noqa: BLE001
        return None

    display_name = cpath.split("::", maxsplit=1)[-1].strip()
    if not display_name:
        return None

    aliases = sorted(
        a
        for a in getattr(ac, "aliases", ())
        if isinstance(a, str) and a and a != display_name
    )
    meta = getattr(ac, "meta", None)
    description = getattr(meta, "description", "") or ""
    usage = _build_usage(ac, display_name)

    return CommandHelpInfo(
        name=display_name,
        description=description,
        aliases=aliases,
        usage=usage,
        admin_only=plugin.plugin_type == "superuser",
    )


def _extract_standard_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    cmds = _extract_rule_commands(getattr(matcher, "rule", None))
    if not cmds:
        return None
    return CommandHelpInfo(
        name=cmds[0],
        aliases=sorted(set(cmds[1:])),
        usage=_cmd_prefix() + cmds[0],
        admin_only=plugin.plugin_type == "superuser",
    )


def _extract_rule_commands(rule: Any) -> list[str]:
    if rule is None:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for checker in getattr(rule, "checkers", ()):
        dep = getattr(checker, "call", None)
        if not isinstance(dep, CommandRule):
            continue
        for tokens in dep.cmds:
            cmd = " ".join(t for t in tokens if isinstance(t, str) and t.strip())
            if cmd and cmd not in seen:
                seen.add(cmd)
                result.append(cmd)
    return result


def _build_usage(ac: Any, command_name: str) -> str:
    prefix = _cmd_prefix()
    parts = [f"{prefix}{command_name}"]
    for arg in getattr(ac, "args", []):
        name = getattr(arg, "name", "").strip()
        if not name or getattr(arg, "hidden", False):
            continue
        wrapper = "[{}]" if getattr(arg, "optional", False) else "<{}>"
        parts.append(wrapper.format(name))
    opts = _build_option_parts(ac)
    return " ".join(parts + opts).strip()


def _build_option_parts(ac: Any) -> list[str]:
    opts: list[str] = []
    for opt in getattr(ac, "options", []):
        if getattr(opt, "dest", "") in {"help", "comp"}:
            continue
        aliases = list(getattr(opt, "aliases", ()) or ())
        name = getattr(opt, "name", "").strip()
        if not aliases and name:
            aliases = [name]
        if not aliases:
            continue
        display = next((a for a in aliases if a.startswith("--")), aliases[0])
        suffix = _build_opt_arg_suffix(opt)
        opts.append(f"[{display}{suffix}]")
    return opts


def _build_opt_arg_suffix(opt: Any) -> str:
    opt_args = getattr(opt, "args", None)
    if opt_args is None or type(opt_args).__name__ == "Empty":
        return ""
    formatted = []
    for a in opt_args:
        an = getattr(a, "name", "").strip()
        if an and not getattr(a, "hidden", False):
            w = "[{}]" if getattr(a, "optional", False) else "<{}>"
            formatted.append(w.format(an))
    return " " + " ".join(formatted) if formatted else ""
