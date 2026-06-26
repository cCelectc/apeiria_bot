"""Generate help menu data from loaded plugins and registered commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.utils.plugin_introspection import get_plugin_extra

from .commands import _collect_matcher_commands
from .discovery import _discover_plugins, _get_loaded_plugin
from .metadata import _merge_declared_commands
from .models import CommandHelpInfo, HelpViewRole, PluginHelpInfo
from .overrides import _apply_overrides, _normalize_commands

if TYPE_CHECKING:
    from .config import HelpConfig

__all__ = [
    "CommandHelpInfo",
    "HelpViewRole",
    "PluginHelpInfo",
    "find_plugin_by_name",
    "generate_help_list",
]


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
