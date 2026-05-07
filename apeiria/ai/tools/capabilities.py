"""Built-in host-action registration for AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import get_loaded_plugins

if TYPE_CHECKING:
    from apeiria.ai.tools.host_actions import AIHostActionRegistry


def register_builtin_capabilities(registry: "AIHostActionRegistry") -> None:
    """Register built-in host-action handlers for the current process."""

    from apeiria.ai.tools.host_actions import (
        AIHostActionContractInput,
        host_action_contract,
    )

    registry.register_action(
        contract=host_action_contract(
            AIHostActionContractInput(
                name="help.show",
                description="Show available built-in AI host actions.",
            )
        ),
        handler=capability_help_show,
    )
    registry.register_action(
        contract=host_action_contract(
            AIHostActionContractInput(
                name="plugin.inspect",
                description="Inspect loaded host plugins.",
                input_schema={
                    "type": "object",
                    "properties": {"plugin_query": {"type": "string"}},
                    "required": ["plugin_query"],
                    "additionalProperties": False,
                },
            )
        ),
        handler=capability_plugin_inspect,
    )


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
