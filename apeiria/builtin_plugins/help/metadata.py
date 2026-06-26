"""Merge declared metadata commands into collected commands."""

from __future__ import annotations

from apeiria.plugins.metadata.api import CommandDeclaration

from .models import CommandHelpInfo


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
