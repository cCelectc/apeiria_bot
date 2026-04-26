from __future__ import annotations

import asyncio
from typing import Any

import pytest
from nonebot.exception import IgnoredException

from apeiria.access.models import PermissionDecision
from apeiria.access.permission import permission_service
from apeiria.bot.feedback import guard_feedback_service
from apeiria.bot.guard import plugin_guard_service


def test_permission_service_calls_denied_handler_before_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = PermissionDecision(allowed=False, code="denied", source="test")
    denied_calls: list[tuple[object, object, PermissionDecision]] = []
    bot: Any = object()
    event: Any = object()
    plugin = object()

    async def fake_check(_bot: object, _event: object, _plugin: object):
        return decision

    async def fake_denied(bot: object, event: object, denied: PermissionDecision):
        denied_calls.append((bot, event, denied))

    monkeypatch.setattr(permission_service, "check_plugin_execution", fake_check)

    with pytest.raises(IgnoredException) as exc_info:
        asyncio.run(
            permission_service.assert_plugin_allowed(
                bot,
                event,
                plugin,
                on_denied=fake_denied,
            )
        )

    assert exc_info.value.args == ("denied",)
    assert denied_calls == [(bot, event, decision)]


def test_plugin_guard_wires_guard_feedback_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_handlers: list[object] = []

    async def fake_assert(
        _bot: object,
        _event: object,
        _plugin: object,
        *,
        on_denied: object | None = None,
    ) -> None:
        captured_handlers.append(on_denied)

    monkeypatch.setattr(permission_service, "assert_plugin_allowed", fake_assert)

    asyncio.run(plugin_guard_service.assert_allowed("bot", "event", "plugin"))

    assert len(captured_handlers) == 1
    handler = captured_handlers[0]
    assert handler is not None
    assert getattr(handler, "__self__", None) is guard_feedback_service
    assert (
        getattr(handler, "__func__", None)
        is type(guard_feedback_service).handle_denied
    )
