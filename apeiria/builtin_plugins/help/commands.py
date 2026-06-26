"""Command extraction from NoneBot matchers and Alconna command formatting."""

from __future__ import annotations

import re
from typing import Any

from nonebot.matcher import matchers
from nonebot.rule import CommandRule

from apeiria.i18n import t
from apeiria.plugins.metadata.api import PluginType
from apeiria.utils.command_prefix import get_command_prefix

from .models import CommandHelpInfo, PluginHelpInfo


def _collect_matcher_commands(
    plugins: dict[str, PluginHelpInfo],
) -> dict[str, list[CommandHelpInfo]]:
    """Collect command information from registered matchers."""
    commands_by_plugin: dict[str, dict[str, CommandHelpInfo]] = {}

    for matcher_group in matchers.values():
        for matcher in matcher_group:
            plugin_id = getattr(matcher, "plugin_name", None)
            if not plugin_id or plugin_id not in plugins:
                continue

            command = _extract_matcher_command(matcher, plugins[plugin_id])
            if command is None:
                continue

            commands_by_plugin.setdefault(plugin_id, {})[command.name] = command

    return {
        plugin_id: sorted(command_map.values(), key=lambda item: item.name)
        for plugin_id, command_map in commands_by_plugin.items()
    }


def _extract_matcher_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    """Extract one command from an Alconna or standard command matcher."""
    command = _extract_alconna_matcher_command(matcher, plugin)
    if command is not None:
        return command
    return _extract_standard_matcher_command(matcher, plugin)


def _extract_alconna_matcher_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    """Extract one command from an Alconna matcher."""
    command_path = getattr(matcher, "_command_path", "")
    command_factory = getattr(matcher, "command", None)
    if not command_path or not callable(command_factory):
        return None

    try:
        alconna_command = command_factory()
    except Exception:  # noqa: BLE001
        return None

    display_name = command_path.split("::", maxsplit=1)[-1].strip()
    if not display_name:
        return None

    aliases = sorted(
        alias
        for alias in getattr(alconna_command, "aliases", ())
        if isinstance(alias, str) and alias and alias != display_name
    )

    meta = getattr(alconna_command, "meta", None)
    description = getattr(meta, "description", "") or ""
    if description == "Unknown":
        description = ""
    usage = _build_usage_text(alconna_command, display_name)
    if not usage:
        get_help = getattr(alconna_command, "get_help", None)
        if callable(get_help):
            try:
                usage = _extract_usage_line(str(get_help()).strip())
            except Exception:  # noqa: BLE001
                usage = ""

    aliases.extend(_extract_shortcut_aliases(matcher, display_name))
    aliases = sorted(set(aliases))

    return CommandHelpInfo(
        name=display_name,
        description=description,
        aliases=aliases,
        usage=usage,
        admin_only=plugin.plugin_type == PluginType.SUPERUSER.value,
    )


def _extract_standard_matcher_command(
    matcher: type[object],
    plugin: PluginHelpInfo,
) -> CommandHelpInfo | None:
    """Extract one command from a standard NoneBot command rule."""
    commands = _extract_rule_commands(getattr(matcher, "rule", None))
    if not commands:
        return None

    display_name = commands[0]
    aliases = sorted({command for command in commands[1:] if command != display_name})
    prefix = get_command_prefix()

    return CommandHelpInfo(
        name=display_name,
        aliases=aliases,
        usage=prefix + display_name,
        admin_only=plugin.plugin_type == PluginType.SUPERUSER.value,
    )


def _extract_rule_commands(rule: Any) -> list[str]:
    if rule is None:
        return []

    raw_commands: list[str] = []
    for checker in getattr(rule, "checkers", ()):
        dependent_call = getattr(checker, "call", None)
        if not isinstance(dependent_call, CommandRule):
            continue
        for command_tokens in dependent_call.cmds:
            command = " ".join(
                token.strip()
                for token in command_tokens
                if isinstance(token, str) and token.strip()
            ).strip()
            if command:
                raw_commands.append(command)

    deduped: list[str] = []
    seen: set[str] = set()
    for command in raw_commands:
        if command in seen:
            continue
        seen.add(command)
        deduped.append(command)
    return deduped


def _extract_shortcut_aliases(
    matcher: type[object],
    command_name: str,
) -> list[str]:
    command_factory = getattr(matcher, "command", None)
    if not callable(command_factory):
        return []

    try:
        command = command_factory()
        get_help = getattr(command, "get_help", None)
        if not callable(get_help):
            return []
        help_text = str(get_help()).strip()
    except Exception:  # noqa: BLE001
        return []

    aliases: list[str] = []
    for line in help_text.splitlines():
        if "=>" not in line:
            continue
        matched = re.search(r"'(.+?)'\s*=>", line)
        if not matched:
            continue

        raw = matched.group(1)
        alias = raw.replace("[!]", "").replace("...args", "").strip()
        alias = alias.replace("...", "").strip()
        alias = alias.split(maxsplit=1)[0].strip("'\" ")
        if alias and alias != command_name:
            aliases.append(alias)
    return aliases


def _extract_usage_line(help_text: str) -> str:
    options_header = t("help.parser.options_header")
    shortcuts_header = t("help.parser.shortcuts_header")
    for line in help_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "Unknown":
            continue
        if stripped.startswith(options_header):
            break
        if stripped.startswith(shortcuts_header):
            break
        return stripped
    return ""


def _build_usage_text(alconna_command: Any, command_name: str) -> str:
    prefix = get_command_prefix()
    parts = [f"{prefix}{command_name}"]

    for arg in getattr(alconna_command, "args", []):
        formatted_arg = _format_arg(arg)
        if formatted_arg:
            parts.append(formatted_arg)

    option_parts: list[str] = []
    for option in getattr(alconna_command, "options", []):
        dest = getattr(option, "dest", "")
        if dest in {"help", "comp"}:
            continue
        formatted_option = _format_option(option)
        if formatted_option:
            option_parts.append(formatted_option)

    return " ".join(parts + option_parts).strip()


def _format_arg(arg: Any) -> str:
    name = getattr(arg, "name", "").strip()
    if not name or getattr(arg, "hidden", False):
        return ""
    display_name = _get_arg_display_name(name)
    wrapper = "[{}]" if getattr(arg, "optional", False) else "<{}>"
    return wrapper.format(display_name)


def _get_arg_display_name(name: str) -> str:
    key = f"help.arg_display.{name}"
    resolved = t(key)
    return name if resolved == key else resolved


def _format_option(option: Any) -> str:
    aliases = list(getattr(option, "aliases", ()) or ())
    if not aliases:
        name = getattr(option, "name", "").strip()
        if not name:
            return ""
        aliases = [name]

    display_name = next(
        (alias for alias in aliases if alias.startswith("--")),
        aliases[0],
    )
    option_args = getattr(option, "args", None)
    if option_args is None or type(option_args).__name__ == "Empty":
        return f"[{display_name}]"

    formatted_args = []
    for arg in option_args:
        formatted = _format_arg(arg)
        if formatted:
            formatted_args.append(formatted)
    suffix = f" {' '.join(formatted_args)}" if formatted_args else ""
    return f"[{display_name}{suffix}]"
