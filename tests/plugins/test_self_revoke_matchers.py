from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot import on_message
from nonebot.adapters import Bot

from apeiria.builtin_plugins.self_revoke.config import SelfRevokeConfig
from tests.plugins.nonebot_helpers import (
    fake_message,
    import_fresh_plugin,
    make_fake_event,
    reply,
)

if TYPE_CHECKING:
    from nonebug import App
    from pytest import MonkeyPatch


class _OneBotV11Bot(Bot):
    @property
    def type(self) -> str:
        return "OneBot V11"


def _onebot_bot(ctx: Any) -> Bot:
    return cast("Bot", ctx.create_bot(base=_OneBotV11Bot, self_id="10000"))


@pytest.mark.anyio
async def test_self_revoke_matchers_pass_and_skip_rules(app: App) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.self_revoke")

    async with app.test_matcher(module._prefixless_revoke) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("ReVoKe"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    async with app.test_matcher(module._prefixless_revoke) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("请撤回"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()

    async with app.test_matcher(module._prefixed_revoke) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("!撤回"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    async with app.test_matcher(module._prefixed_revoke) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("撤回"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


@pytest.mark.anyio
async def test_self_revoke_matcher_calls_platform_api(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.self_revoke")
    monkeypatch.setattr(
        module,
        "get_self_revoke_config",
        _self_revoke_no_trigger_config,
    )

    async with app.test_matcher(module._prefixless_revoke) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            self_id="10000",
            user_id="20000",
            message_id=123,
            message=fake_message("撤回"),
            reply=reply(456, user_id="10000"),
        )

        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()
        ctx.should_call_api("delete_msg", {"message_id": 456}, result=None)


@pytest.mark.anyio
async def test_self_revoke_ignored_event_keeps_propagating(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.self_revoke")
    monkeypatch.setattr(
        module,
        "get_self_revoke_config",
        _self_revoke_default_config,
    )
    propagated: list[str] = []
    sentinel = on_message(priority=9, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._prefixless_revoke, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(message=fake_message("撤回"))
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._prefixless_revoke)
            ctx.should_pass_rule(module._prefixless_revoke)
            ctx.should_pass_permission(sentinel)
            ctx.should_pass_rule(sentinel)
    finally:
        sentinel.destroy()

    assert propagated == ["ran"]


@pytest.mark.anyio
async def test_self_revoke_handled_event_stops_later_matchers(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.self_revoke")
    monkeypatch.setattr(
        module,
        "get_self_revoke_config",
        _self_revoke_no_trigger_config,
    )
    propagated: list[str] = []
    sentinel = on_message(priority=9, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._prefixless_revoke, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(
                self_id="10000",
                message=fake_message("撤回"),
                reply=reply(456, user_id="10000"),
            )
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._prefixless_revoke)
            ctx.should_pass_rule(module._prefixless_revoke)
            ctx.should_call_api("delete_msg", {"message_id": 456}, result=None)
    finally:
        sentinel.destroy()

    assert propagated == []


def _self_revoke_default_config() -> SelfRevokeConfig:
    return SelfRevokeConfig()


def _self_revoke_no_trigger_config() -> SelfRevokeConfig:
    return SelfRevokeConfig(revoke_trigger_message=False)
