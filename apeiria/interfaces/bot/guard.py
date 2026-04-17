"""Unified runtime guard for plugin execution."""

from __future__ import annotations

from apeiria.app.access import PermissionDecision, permission_service


class PluginGuardService:
    """Evaluate plugin runtime access for all incoming matcher executions."""

    async def evaluate(self, bot, event, plugin) -> PermissionDecision:  # noqa: ANN001
        return await permission_service.check_plugin_execution(bot, event, plugin)

    async def assert_allowed(self, bot, event, plugin) -> None:  # noqa: ANN001
        await permission_service.assert_plugin_allowed(bot, event, plugin)


plugin_guard_service = PluginGuardService()
