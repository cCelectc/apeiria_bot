"""Generate help menu data from loaded plugins and registered commands."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import md5
from typing import TYPE_CHECKING, Any, Literal

import nonebot
from nonebot.matcher import matchers
from nonebot.rule import CommandRule

from apeiria.builtin_plugins.help.utils import find_plugin_icon
from apeiria.i18n import t
from apeiria.plugins.metadata.api import CommandDeclaration, PluginType
from apeiria.utils.command_prefix import get_command_prefix
from apeiria.utils.plugin_introspection import (
    get_plugin_extra,
    get_plugin_name,
    get_plugin_source,
)

if TYPE_CHECKING:
    from apeiria.builtin_plugins.help.config import (
        HelpConfig,
        PluginOverride,
    )

HelpViewRole = Literal["user", "admin", "owner"]


@dataclass(slots=True)
class CommandHelpInfo:
    """Help information for one command."""

    name: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    usage: str = ""
    admin_only: bool = False
    custom_prefix: str | None = None

    @property
    def cache_key(self) -> str:
        return f"{self.name}|{self.description}|{self.usage}|{self.custom_prefix}"


@dataclass(slots=True)
class PluginHelpInfo:
    """Help information for a single plugin."""

    plugin_id: str
    module_name: str
    name: str
    display_name: str
    description: str
    usage: str
    plugin_type: str
    admin_level: int
    version: str
    source: str
    icon_url: str
    menu_category: str = ""
    introduction: str = ""
    precautions: list[str] = field(default_factory=list)
    owner_help: str = ""
    commands: list[CommandHelpInfo] = field(default_factory=list)
    order: int = 99

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"

    @property
    def initials(self) -> str:
        compact = "".join(ch for ch in self.display_name if ch.isalnum())
        if compact:
            return compact[:2].upper()
        stripped = self.display_name.strip()
        return stripped[:2] or "?"

    @property
    def accent_color(self) -> str:
        digest = md5(self.module_name.encode("utf-8")).hexdigest()
        hue = int(digest[:2], 16) % 360
        return f"hsl({hue} 68% 56%)"

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def cache_key(self) -> str:
        command_key = ",".join(command.cache_key for command in self.commands)
        return (
            f"{self.plugin_id}|{self.display_name}|{self.description}|"
            f"{self.icon_url}|{self.menu_category}|{self.introduction}|"
            f"{','.join(self.precautions)}|{self.owner_help}|{command_key}|{self.order}"
        )


def generate_help_list(
    config: HelpConfig,
    *,
    role: HelpViewRole = "user",
    show_all: bool = False,
) -> list[PluginHelpInfo]:
    """Generate help list from loaded plugins and registered matchers."""
    plugins = _discover_plugins(config, role=role, show_all=show_all)
    command_index = _collect_matcher_commands(plugins)

    result: list[PluginHelpInfo] = []
    for plugin in plugins.values():
        commands = command_index.get(plugin.plugin_id, [])
        loaded_plugin = _get_loaded_plugin(plugin.plugin_id)
        extra = get_plugin_extra(loaded_plugin) if loaded_plugin is not None else None
        if extra:
            commands = _merge_declared_commands(commands, extra.commands)

        plugin.commands = sorted(commands, key=lambda item: item.name)
        result.append(plugin)

    _apply_overrides(result, config.plugin_overrides)
    for plugin in result:
        plugin.commands = _normalize_commands(plugin.commands)

    result = [plugin for plugin in result if plugin.commands]
    result.sort(
        key=lambda item: (
            item.order,
            0 if item.is_builtin else 1,
            item.display_name.lower(),
        )
    )
    return result


def find_plugin_by_name(
    name: str,
    config: HelpConfig,
    *,
    role: HelpViewRole = "user",
    show_all: bool = False,
) -> PluginHelpInfo | None:
    """Find a plugin by display name or module name."""
    all_plugins = generate_help_list(config, role=role, show_all=show_all)
    name_lower = name.lower()
    for plugin in all_plugins:
        if (
            plugin.display_name.lower() == name_lower
            or plugin.name.lower() == name_lower
            or plugin.module_name.lower() == name_lower
            or plugin.plugin_id.lower() == name_lower
        ):
            return plugin
    for plugin in all_plugins:
        if (
            name_lower in plugin.display_name.lower()
            or name_lower in plugin.name.lower()
            or name_lower in plugin.module_name.lower()
            or name_lower in plugin.plugin_id.lower()
        ):
            return plugin
    return None


def _discover_plugins(
    config: HelpConfig,
    *,
    role: HelpViewRole,
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
            extra.admin_level,
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
            admin_level=extra.admin_level if extra else 0,
            version=extra.version if extra else "",
            source=source,
            icon_url=icon_url,
            menu_category=extra.menu_category.strip() if extra else "",
            introduction=extra.introduction.strip() if extra else "",
            precautions=[item.strip() for item in extra.precautions] if extra else [],
            owner_help=extra.owner_help.strip() if extra else "",
        )

    return result


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
        admin_only=plugin.admin_level > 0,
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
        admin_only=plugin.admin_level > 0,
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


def _merge_declared_commands(
    existing: list[CommandHelpInfo],
    declared: list[str | CommandDeclaration],
) -> list[CommandHelpInfo]:
    """Merge declared metadata commands into collected commands."""
    merged = {command.name: command for command in existing}
    for item in declared:
        command = _command_from_declaration(item)
        if command is None:
            continue
        existing_command = merged.get(command.name)
        if existing_command is None:
            merged[command.name] = command
            continue
        merged[command.name] = CommandHelpInfo(
            name=existing_command.name,
            description=existing_command.description or command.description,
            aliases=sorted(set(existing_command.aliases) | set(command.aliases)),
            usage=existing_command.usage or command.usage,
            admin_only=existing_command.admin_only or command.admin_only,
            custom_prefix=(
                existing_command.custom_prefix
                if existing_command.custom_prefix is not None
                else command.custom_prefix
            ),
        )
    return list(merged.values())


def _command_from_declaration(
    value: str | CommandDeclaration,
) -> CommandHelpInfo | None:
    if isinstance(value, str):
        name = value.strip()
        return CommandHelpInfo(name=name) if name else None
    if not isinstance(value, CommandDeclaration):
        return None
    name = value.name.strip()
    if not name:
        return None
    return CommandHelpInfo(
        name=name,
        description=value.description.strip(),
        aliases=sorted(
            alias.strip()
            for alias in value.aliases
            if isinstance(alias, str) and alias.strip() and alias.strip() != name
        ),
        usage=value.usage.strip(),
        custom_prefix=value.custom_prefix,
    )


def _apply_overrides(
    plugins: list[PluginHelpInfo],
    overrides: list[PluginOverride],
) -> None:
    """Apply plugin display overrides."""
    plugin_map = {plugin.plugin_id: plugin for plugin in plugins}
    plugin_map.update({plugin.name: plugin for plugin in plugins})
    plugin_map.update({plugin.module_name: plugin for plugin in plugins})

    for override in overrides:
        target = plugin_map.get(override.plugin_name)
        if target is None:
            module_name = f"override.{override.plugin_name or 'plugin'}"
            target = PluginHelpInfo(
                plugin_id=module_name,
                module_name=module_name,
                name=override.plugin_name or t("help.defaults.unnamed_plugin"),
                display_name=override.plugin_name or t("help.defaults.unnamed_plugin"),
                description="",
                usage="",
                plugin_type="custom",
                admin_level=0,
                version="",
                source="custom",
                icon_url=find_plugin_icon(None, seed=module_name),
                menu_category="",
                introduction="",
                precautions=[],
                owner_help="",
                order=override.order,
            )
            plugins.append(target)
            plugin_map[target.plugin_id] = target
            plugin_map[target.name] = target
            plugin_map[target.module_name] = target

        if override.display_name:
            target.display_name = override.display_name
        if override.description:
            target.description = override.description
        if override.category:
            target.menu_category = override.category
        target.order = override.order

        for raw_command in override.extra_commands:
            command = _parse_pipe_command(raw_command)
            if command is None:
                continue
            target.commands = [
                item for item in target.commands if item.name != command.name
            ]
            target.commands.append(command)


def _plugin_visible_in_role(
    plugin_type: PluginType,
    admin_level: int,
    role: HelpViewRole,
) -> bool:
    if role == "owner":
        return True
    if role == "admin":
        return plugin_type == PluginType.NORMAL
    return plugin_type == PluginType.NORMAL and admin_level <= 0


def _parse_pipe_command(raw: str) -> CommandHelpInfo | None:
    """Parse the `command|description|prefix` format."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    parts = [item.strip() for item in raw.split("|")]
    name = parts[0]
    if not name:
        return None
    description = parts[1] if len(parts) > 1 else ""
    custom_prefix = parts[2] if len(parts) > 2 else None  # noqa: PLR2004
    return CommandHelpInfo(
        name=name,
        description=description,
        custom_prefix=custom_prefix,
    )


def _normalize_commands(commands: list[CommandHelpInfo]) -> list[CommandHelpInfo]:
    """Deduplicate commands and normalize aliases for stable rendering."""
    merged: dict[str, CommandHelpInfo] = {}
    for command in commands:
        existing = merged.get(command.name)
        aliases = sorted(
            {
                alias.strip()
                for alias in command.aliases
                if isinstance(alias, str)
                and alias.strip()
                and alias.strip() != command.name
            }
        )
        normalized = CommandHelpInfo(
            name=command.name,
            description=command.description.strip(),
            aliases=aliases,
            usage=command.usage.strip(),
            admin_only=command.admin_only,
            custom_prefix=command.custom_prefix,
        )
        if existing is None:
            merged[command.name] = normalized
            continue
        merged[command.name] = CommandHelpInfo(
            name=existing.name,
            description=existing.description or normalized.description,
            aliases=sorted(set(existing.aliases) | set(normalized.aliases)),
            usage=existing.usage or normalized.usage,
            admin_only=existing.admin_only or normalized.admin_only,
            custom_prefix=(
                existing.custom_prefix
                if existing.custom_prefix is not None
                else normalized.custom_prefix
            ),
        )
    return sorted(merged.values(), key=lambda item: item.name)


def _get_loaded_plugin(plugin_id: str):
    for plugin in nonebot.get_loaded_plugins():
        if plugin.id_ == plugin_id:
            return plugin
    return None


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
