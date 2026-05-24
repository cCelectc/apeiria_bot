from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot import on
from nonebot.adapters import Bot

from apeiria.builtin_plugins.contact_approval.config import ContactApprovalConfig
from apeiria.builtin_plugins.contact_approval.service import (
    ContactApprovalHandleResult,
)
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
async def test_contact_approval_request_matcher_delegates_and_stops(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.contact_approval")
    handled: list[tuple[str, str]] = []
    propagated: list[str] = []

    async def fake_request(
        bot: Bot,
        event: Any,
        *,
        config: ContactApprovalConfig | None = None,
    ) -> ContactApprovalHandleResult:
        assert isinstance(config, ContactApprovalConfig)
        handled.append((bot.self_id, event.flag))
        return ContactApprovalHandleResult(
            status="notified",
            should_stop_propagation=True,
        )

    monkeypatch.setattr(module, "handle_request_event", fake_request)
    sentinel = on("request", priority=3, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._request, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(
                event_type="request",
                request_type="friend",
                flag="friend-flag",
                message=fake_message(""),
            )
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._request)
            ctx.should_pass_rule(module._request)
    finally:
        sentinel.destroy()

    assert handled == [("10000", "friend-flag")]
    assert propagated == []


@pytest.mark.anyio
async def test_contact_approval_message_rule_matches_commands(app: App) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.contact_approval")

    async def fake_message_handler(
        bot: Bot,
        event: Any,
        *,
        message_text: str,
        reply_message_id: str | None = None,
        config: ContactApprovalConfig | None = None,
    ) -> ContactApprovalHandleResult:
        assert bot is not None
        assert event is not None
        assert message_text == "同意"
        assert reply_message_id == "msg-1"
        assert isinstance(config, ContactApprovalConfig)
        return ContactApprovalHandleResult(status="not_handled")

    module.handle_approval_message = fake_message_handler

    async with app.test_matcher(module._approval) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            message=fake_message("同意"),
            reply=reply("msg-1"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    async with app.test_matcher(module._approval) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("普通消息"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


@pytest.mark.anyio
async def test_contact_approval_matcher_sends_ticket_not_found_reply(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.contact_approval")
    config = ContactApprovalConfig()
    monkeypatch.setattr(module, "get_contact_approval_config", lambda: config)

    async with app.test_matcher(module._approval) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            user_id="123456",
            message=fake_message("同意 #NOPE"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()
        ctx.should_call_send(event, config.ticket_not_found_reply, result=None)
