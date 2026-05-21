"""Unified runtime guard for plugin execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeAlias

from apeiria.access.permission import permission_service
from apeiria.bot.event_context import build_access_context_from_event
from apeiria.bot.feedback import guard_feedback_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.access import PermissionDecision

DeniedFeedbackHandler: TypeAlias = Callable[
    ["Bot", "Event", "PermissionDecision"], Awaitable[None]
]


class PluginGuardService:
    """Evaluate plugin runtime access for all incoming matcher executions."""

    async def evaluate(
        self,
        bot: "Bot",
        event: "Event",
        plugin: object,
    ) -> "PermissionDecision":
        context = build_access_context_from_event(bot, event)
        if context is None:
            return permission_service.allow()
        return await permission_service.check_plugin_execution(
            context,
            plugin_module=plugin.module_name,  # type: ignore[attr-defined]
        )

    async def assert_allowed(
        self,
        bot: "Bot",
        event: "Event",
        plugin: object,
        *,
        on_denied: DeniedFeedbackHandler | None = guard_feedback_service.handle_denied,
    ) -> None:
        from nonebot.exception import IgnoredException

        decision = await self.evaluate(bot, event, plugin)
        if decision.allowed:
            return
        if on_denied is not None:
            await on_denied(bot, event, decision)
        raise IgnoredException(decision.code)


plugin_guard_service = PluginGuardService()
