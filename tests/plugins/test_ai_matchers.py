from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot.adapters import Bot

from tests.plugins.nonebot_helpers import (
    fake_text_segments,
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
async def test_ai_message_matcher_does_not_accept_without_selectable_model(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.ai")

    async def fake_has_selectable_task_model(**_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(
        module,
        "has_selectable_task_model",
        fake_has_selectable_task_model,
    )

    async with app.test_matcher(module.ai_message) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_text_segments("hello"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


@pytest.mark.anyio
async def test_ai_message_matcher_accepts_with_selectable_model(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.ai")

    async def fake_has_selectable_task_model(**_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(
        module,
        "has_selectable_task_model",
        fake_has_selectable_task_model,
    )

    async with app.test_matcher(module.ai_message) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_text_segments("hello"),
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()


@pytest.mark.anyio
async def test_ai_message_matcher_rechecks_model_readiness_dynamically(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.ai")
    readiness = {"enabled": False}

    async def fake_has_selectable_task_model(**_kwargs: object) -> bool:
        return readiness["enabled"]

    monkeypatch.setattr(
        module,
        "has_selectable_task_model",
        fake_has_selectable_task_model,
    )

    async with app.test_matcher(module.ai_message) as ctx:
        bot = _onebot_bot(ctx)
        first_event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_text_segments("first"),
        )
        ctx.receive_event(bot, first_event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()

    readiness["enabled"] = True

    async with app.test_matcher(module.ai_message) as ctx:
        bot = _onebot_bot(ctx)
        second_event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_text_segments("second"),
        )
        ctx.receive_event(bot, second_event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()

    readiness["enabled"] = False

    async with app.test_matcher(module.ai_message) as ctx:
        bot = _onebot_bot(ctx)
        third_event = make_fake_event(
            user_id="20000",
            group_id="30000",
            message=fake_text_segments("third"),
        )
        ctx.receive_event(bot, third_event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()
