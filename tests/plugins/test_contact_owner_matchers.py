from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot.adapters import Bot

from apeiria.builtin_plugins.contact_owner.config import ContactOwnerConfig
from apeiria.builtin_plugins.contact_owner.service import ContactOwnerHandleResult
from tests.plugins.nonebot_helpers import (
    fake_message,
    import_fresh_plugin,
    make_fake_event,
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
async def test_contact_owner_rule_matches_configured_prefix(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.contact_owner")
    monkeypatch.setattr(
        module,
        "get_contact_owner_config",
        lambda: ContactOwnerConfig(
            contact_prefix="找主人",
            owner_target="qq:123456",
        ),
    )

    async def fake_handler(
        *_args: object,
        **_kwargs: object,
    ) -> ContactOwnerHandleResult:
        return ContactOwnerHandleResult(status="ignored")

    monkeypatch.setattr(module, "handle_contact_owner_event", fake_handler)

    async with app.test_matcher(module._contact_owner) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("  找主人 帮我看看"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    async with app.test_matcher(module._contact_owner) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("请找主人"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


@pytest.mark.anyio
async def test_contact_owner_matcher_delivers_and_replies(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.contact_owner")
    config = ContactOwnerConfig(owner_target="qq:123456")
    monkeypatch.setattr(module, "get_contact_owner_config", lambda: config)

    async with app.test_matcher(module._contact_owner) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_message("联系主人 帮我看看"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()
        ctx.should_call_api(
            "send_private_msg",
            {
                "user_id": 123456,
                "message": (
                    "收到一条联系主人留言：\n\n"
                    "帮我看看\n\n"
                    "来源：\n"
                    "- 用户 ID：20000\n"
                    "- 群 ID：30000\n"
                    "- 消息 ID：123"
                ),
            },
            result=None,
        )
        ctx.should_call_send(event, config.success_reply, result=None)
