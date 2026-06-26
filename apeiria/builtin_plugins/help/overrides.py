"""Apply plugin display overrides and normalize commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.builtin_plugins.help.utils import find_plugin_icon
from apeiria.i18n import t

from .models import CommandHelpInfo, PluginHelpInfo

if TYPE_CHECKING:
    from .config import PluginOverride


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
