"""Built-in capability registration for the AI tool bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nonebot

from apeiria.shared.plugin_introspection import get_plugin_name

if TYPE_CHECKING:
    from apeiria.app.ai.tools.bridge import AINoneBotCapabilityBridge


def register_builtin_capabilities(bridge: "AINoneBotCapabilityBridge") -> None:
    """Register built-in whitelist capability handlers."""

    bridge.register("help.show", capability_help_show)
    bridge.register("plugin.inspect", capability_plugin_inspect)


async def capability_help_show(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a compact help summary from loaded plugins."""

    topic = str(payload.get("topic", "plugins")).strip() or "plugins"
    plugins = [
        plugin
        for plugin in nonebot.get_loaded_plugins()
        if plugin.module_name and "help" not in plugin.module_name
    ]
    return {
        "topic": topic,
        "count": len(plugins),
        "plugins": [get_plugin_name(plugin) for plugin in plugins[:8]],
    }


async def capability_plugin_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary for one loaded plugin."""

    query = str(payload.get("plugin_query", "")).strip()
    if not query:
        return {
            "plugin_query": "",
            "plugin_name": "",
            "module_name": "",
            "description": "",
            "usage": "",
        }

    plugin = _find_plugin_by_query(query)
    if plugin is None:
        return {
            "plugin_query": query,
            "plugin_name": "",
            "module_name": "",
            "description": "",
            "usage": "",
        }

    description = getattr(plugin.metadata, "description", "") or ""
    usage = getattr(plugin.metadata, "usage", "") or ""
    return {
        "plugin_query": query,
        "plugin_name": get_plugin_name(plugin),
        "module_name": plugin.module_name,
        "description": description,
        "usage": usage,
    }


def _find_plugin_by_query(query: str):
    normalized = query.strip().lower()
    if not normalized:
        return None

    for plugin in nonebot.get_loaded_plugins():
        module_name = (plugin.module_name or "").lower()
        plugin_name = get_plugin_name(plugin).strip().lower()
        if normalized in (module_name, plugin_name):
            return plugin
        if normalized in module_name or normalized in plugin_name:
            return plugin
    return None
