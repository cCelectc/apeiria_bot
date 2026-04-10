"""Built-in capability registration for the AI skill bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import get_loaded_plugins

if TYPE_CHECKING:
    from apeiria.app.ai.skills.bridge import AINoneBotSkillBridge


def register_builtin_capabilities(bridge: "AINoneBotSkillBridge") -> None:
    """Register built-in capability handlers for the current process."""

    bridge.register("help.show", capability_help_show)
    bridge.register("plugin.inspect", capability_plugin_inspect)


def capability_help_show(_: dict[str, object]) -> dict[str, object]:
    """Return a minimal help capability payload."""

    return {
        "status": "ok",
        "summary": "help capability is available",
    }


def capability_plugin_inspect(arguments: dict[str, object]) -> dict[str, object]:
    """Return a minimal plugin inspection payload."""

    query = str(arguments.get("plugin_query", "")).strip().lower()
    plugins = sorted(
        plugin.module_name
        for plugin in get_loaded_plugins()
        if getattr(plugin, "module_name", None)
    )
    match = next((name for name in plugins if query and query in name.lower()), None)
    return {
        "status": "ok",
        "plugin_query": query,
        "plugin_name": match,
        "matches": plugins[:20],
    }
