from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot.adapters import Bot

from apeiria.builtin_plugins.repeater.config import RepeaterConfig
from apeiria.builtin_plugins.repeater.service import RepeaterService
from tests.plugins.nonebot_helpers import (
    fake_text_segments,
    import_fresh_plugin,
    make_fake_event,
)

if TYPE_CHECKING:
    from nonebug import App
    from pytest import MonkeyPatch


class _QQBot(Bot):
    @property
    def type(self) -> str:
        return "qq"


def _qq_bot(ctx: Any) -> Bot:
    return cast("Bot", ctx.create_bot(base=_QQBot, self_id="bot"))


@pytest.mark.anyio
async def test_repeater_matcher_rules_filter_configured_groups(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.repeater")
    monkeypatch.setattr(module, "get_repeater_config", _active_repeater_config)

    async with app.test_matcher(module._repeater) as ctx:
        bot = _qq_bot(ctx)
        event = make_fake_event(
            group_id="100",
            user_id="u1",
            message=fake_text_segments("哈"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    async with app.test_matcher(module._repeater) as ctx:
        bot = _qq_bot(ctx)
        event = make_fake_event(
            group_id="200",
            user_id="u1",
            message=fake_text_segments("哈"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()

    async with app.test_matcher(module._repeater) as ctx:
        bot = _qq_bot(ctx)
        event = make_fake_event(
            group_id=None,
            user_id="u1",
            message=fake_text_segments("哈"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


@pytest.mark.anyio
async def test_repeater_matcher_sends_on_repeated_group_text(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.repeater")
    service = RepeaterService(random_draw=lambda: 0.0)
    monkeypatch.setattr(module, "get_repeater_config", _active_repeater_config)
    monkeypatch.setattr(module, "default_repeater_service", service)

    async with app.test_matcher(module._repeater) as ctx:
        bot = _qq_bot(ctx)
        first_event = make_fake_event(
            group_id="100",
            user_id="u1",
            message=fake_text_segments("哈"),
        )
        second_message = fake_text_segments("哈")
        second_event = make_fake_event(
            group_id="100",
            user_id="u2",
            message=second_message,
        )
        ctx.receive_event(bot, first_event)
        ctx.should_pass_permission(module._repeater)
        ctx.should_pass_rule(module._repeater)
        ctx.receive_event(bot, second_event)
        ctx.should_pass_permission(module._repeater)
        ctx.should_pass_rule(module._repeater)
        ctx.should_call_send(second_event, second_message, result=None)


def _active_repeater_config() -> RepeaterConfig:
    return RepeaterConfig(
        repeat_threshold=2,
        platforms=("qq",),
        group_mode="allowlist",
        allow_groups=frozenset({"qq:100"}),
    )
