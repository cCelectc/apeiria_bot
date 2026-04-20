"""Helpers for resolving the display command prefix."""

from __future__ import annotations

import nonebot


def get_command_prefix() -> str:
    """Return one display prefix from Alconna or NoneBot config."""
    alconna_prefix = _get_alconna_prefix()
    if alconna_prefix:
        return alconna_prefix

    command_start_prefix = _get_nonebot_command_start()
    if command_start_prefix:
        return command_start_prefix

    return "/"


def _get_alconna_prefix() -> str | None:
    try:
        from arclet.alconna import config as alconna_config
        from nonebot.plugin import get_plugin_config
        from nonebot_plugin_alconna.config import Config as AlconnaConfig

        prefixes = getattr(alconna_config.default_namespace, "prefixes", ())
        resolved = _pick_prefix(prefixes)
        if resolved:
            return resolved

        config = get_plugin_config(AlconnaConfig)
        if getattr(config, "alconna_use_command_start", False):
            return _get_nonebot_command_start()
    except Exception:  # noqa: BLE001
        return None
    return None


def _get_nonebot_command_start() -> str | None:
    try:
        command_start = getattr(nonebot.get_driver().config, "command_start", None)
    except Exception:  # noqa: BLE001
        return None
    return _pick_prefix(command_start)


def _pick_prefix(value: object) -> str | None:
    if isinstance(value, set) and value:
        items = sorted(str(item) for item in value if item)
        return items[0] if items else None
    if isinstance(value, (list, tuple)) and value:
        first = str(value[0])
        return first or None
    if isinstance(value, str) and value:
        return value
    return None
