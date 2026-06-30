from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import nonebot
from nonebot.log import logger
from nonebot.permission import SUPERUSER as SUPERUSER_PERM
from nonebot.rule import CommandRule

from .models import HelpCommandItem, HelpPluginItem

if TYPE_CHECKING:
    from .config import HelpConfig

_FRAMEWORK_PREFIX = "apeiria."
_THIRD_PARTY_PREFIXES = ("nonebot_plugin_", "nonebot.")


def _plugin_source(plugin: Any) -> str:
    module_file = getattr(getattr(plugin, "module", None), "__file__", None) or ""
    module_name = plugin.module_name or ""
    if "builtin_plugins" in module_file or module_name.startswith(
        "apeiria.builtin_plugins"
    ):
        return "builtin"
    if module_name.startswith(_FRAMEWORK_PREFIX):
        return "framework"
    if module_name.startswith(_THIRD_PARTY_PREFIXES):
        return "third_party"
    return "user"


def _find_icon(plugin: Any) -> str:
    module_file = getattr(getattr(plugin, "module", None), "__file__", None)
    if module_file:
        base = Path(module_file).resolve().parent
        for ext in ("png", "webp", "jpg", "jpeg", "svg"):
            p = base / f"logo.{ext}"
            if p.is_file():
                import base64

                mime = f"image/{'svg+xml' if ext == 'svg' else ext}"
                data = p.read_bytes()
                return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    return "https://nonebot.dev/logo.png"


def _probe_admin_only(matcher: Any) -> bool:
    try:
        handlers = getattr(matcher.permission, "checkers", set())
        if SUPERUSER_PERM.checkers & handlers:
            return True
        if matcher.permission is SUPERUSER_PERM:
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _build_usage(ac: Any, command_name: str) -> str:
    parts = [command_name]
    for arg in getattr(ac, "args", []):
        aname = getattr(arg, "name", "").strip()
        if not aname or getattr(arg, "hidden", False):
            continue
        wrapper = "[{}]" if getattr(arg, "optional", False) else "<{}>"
        parts.append(wrapper.format(aname))
    for opt in getattr(ac, "options", []):
        if getattr(opt, "dest", "") in {"help", "comp"}:
            continue
        aliases = list(getattr(opt, "aliases", ()) or ())
        oname = getattr(opt, "name", "").strip()
        if not aliases and oname:
            aliases = [oname]
        if not aliases:
            continue
        display = next((a for a in aliases if a.startswith("--")), aliases[0])
        parts.append(f"[{display}]")
    return " ".join(parts)


def probe_commands(plugin: Any) -> list[HelpCommandItem]:
    commands: list[HelpCommandItem] = []
    added: set[str] = set()
    admin_only = False

    for mgroup in nonebot.matcher.matchers.values():
        for matcher in mgroup:
            pid = getattr(matcher, "plugin_id", None)
            if not pid or pid != plugin.id_:
                continue

            try:
                is_admin = _probe_admin_only(matcher)
                admin_only = admin_only or is_admin

                for cmd in _try_extract_matcher_cmds(matcher):
                    if cmd.name in added:
                        existing = next(c for c in commands if c.name == cmd.name)
                        if cmd.aliases:
                            existing.aliases = sorted(
                                set(existing.aliases) | set(cmd.aliases) - {cmd.name}
                            )
                        if cmd.description:
                            existing.description = (
                                existing.description or cmd.description
                            )
                        if cmd.usage:
                            existing.usage = existing.usage or cmd.usage
                        existing.admin_only = existing.admin_only or cmd.admin_only
                        continue
                    added.add(cmd.name)
                    cmd.admin_only = cmd.admin_only or is_admin
                    commands.append(cmd)
            except Exception:  # noqa: BLE001
                logger.opt(exception=True).debug(
                    "Command probing failed for matcher in plugin {}",
                    plugin.id_,
                )

    return commands


def _try_extract_matcher_cmds(matcher: Any) -> list[HelpCommandItem]:
    results: list[HelpCommandItem] = []
    alconna_results = _probe_alconna(matcher)
    results.extend(alconna_results)
    if alconna_results:
        return results  # alconna already covers all commands for this matcher
    cmdrule_results = _probe_command_rule(matcher)
    results.extend(cmdrule_results)
    return results


def _probe_alconna(matcher: Any) -> list[HelpCommandItem]:
    factory = getattr(matcher, "command", None)
    if not callable(factory):
        return []
    try:
        ac = factory()
    except Exception:  # noqa: BLE001
        return []

    cmd_path = getattr(matcher, "_command_path", "")
    name = cmd_path.split("::", maxsplit=1)[-1].strip() if cmd_path else ""
    if not name:
        name = ac.command
    if not name:
        return []

    if "::" in name:
        name = name.split("::")[-1].strip()
    if not name:
        return []

    aliases = sorted(
        a for a in getattr(ac, "aliases", ()) if isinstance(a, str) and a and a != name
    )
    meta = getattr(ac, "meta", None)
    description = getattr(meta, "description", "") or ""
    usage = _build_usage(ac, name)

    return [
        HelpCommandItem(
            name=name,
            aliases=aliases,
            description=description,
            usage=usage,
        )
    ]


def _probe_command_rule(matcher: Any) -> list[HelpCommandItem]:
    rule = getattr(matcher, "rule", None)
    if rule is None:
        return []
    cmds = _extract_rule_commands(rule)
    if not cmds:
        return []
    result = [HelpCommandItem(name=cmds[0], usage=cmds[0])]
    if len(cmds) > 1:
        result[0].aliases = sorted(set(cmds[1:]))
    return result


def _extract_rule_commands(rule: Any) -> list[str]:
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


def discover_plugins(
    config: HelpConfig,
    *,
    is_superuser: bool,
    show_all: bool = False,
) -> list[HelpPluginItem]:
    blacklist: set[str] = set() if show_all else set(config.hidden_plugins)
    result: list[HelpPluginItem] = []

    for plugin in nonebot.get_loaded_plugins():
        meta = plugin.metadata
        if not meta:
            continue

        source = _plugin_source(plugin)

        if (
            not is_superuser
            and not config.show_builtin_plugins
            and source in {"builtin", "framework"}
        ):
            continue

        if plugin.id_ in blacklist or plugin.module_name in blacklist:
            continue

        icon_url = _find_icon(plugin)
        commands = probe_commands(plugin)

        result.append(
            HelpPluginItem(
                plugin_id=plugin.id_,
                module_name=plugin.module_name,
                name=meta.name or plugin.module_name,
                description=meta.description or "",
                usage=meta.usage or "",
                plugin_type=getattr(meta, "type", "application") or "application",
                source=source,
                icon_url=icon_url,
                commands=commands,
            )
        )

    app_plugins = [p for p in result if not p.is_builtin]
    builtin_plugins = [p for p in result if p.is_builtin]
    return app_plugins + builtin_plugins


def find_plugin_by_name(
    name: str,
    config: HelpConfig,
    *,
    is_superuser: bool,
    show_all: bool = False,
) -> HelpPluginItem | None:
    plugins = discover_plugins(config, is_superuser=is_superuser, show_all=show_all)
    nl = name.lower()
    methods = (
        lambda p: p.name.lower(),
        lambda p: p.module_name.lower(),
    )
    for method in methods:
        for p in plugins:
            if nl == method(p):
                return p
    for method in methods:
        for p in plugins:
            if nl in method(p):
                return p
    return None
