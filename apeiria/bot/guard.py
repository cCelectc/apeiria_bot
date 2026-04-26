"""Unified runtime guard for plugin execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.access.permission import permission_service
from apeiria.bot.feedback import guard_feedback_service

if TYPE_CHECKING:
    from apeiria.access import PermissionDecision


class PluginGuardService:
    """Evaluate plugin runtime access for all incoming matcher executions."""

    async def evaluate(self, bot, event, plugin) -> PermissionDecision:  # noqa: ANN001
        return await permission_service.check_plugin_execution(bot, event, plugin)

    async def assert_allowed(self, bot, event, plugin) -> None:  # noqa: ANN001
        await permission_service.assert_plugin_allowed(
            bot,
            event,
            plugin,
            on_denied=guard_feedback_service.handle_denied,
        )


plugin_guard_service = PluginGuardService()
