from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from nonebot import on_message
from nonebot.adapters import Bot

from apeiria.builtin_plugins.trigger_reply.config import TriggerReplyConfig
from apeiria.builtin_plugins.trigger_reply.models import (
    TriggerCooldown,
    TriggerEntry,
    TriggerMatch,
    TriggerReply,
    TriggerRuleSet,
)
from apeiria.builtin_plugins.trigger_reply.service import (
    TriggerReplyCooldownStore,
    TriggerReplyService,
)
from tests.plugins.nonebot_helpers import (
    fake_message,
    import_fresh_plugin,
    make_fake_event,
)

if TYPE_CHECKING:
    from pathlib import Path

    from nonebug import App
    from pytest import MonkeyPatch


class _OneBotV11Bot(Bot):
    @property
    def type(self) -> str:
        return "OneBot V11"


def _onebot_bot(ctx: Any) -> Bot:
    return cast("Bot", ctx.create_bot(base=_OneBotV11Bot, self_id="10000"))


def test_reload_function_replaces_active_cached_ruleset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[new]
reply = "new reply"
type = "full"
match = "new"
""",
        encoding="utf-8",
    )
    module.default_rule_set_cache.set(
        TriggerRuleSet(
            entries=(
                _entry(
                    "old",
                    matches=(TriggerMatch(type="full", pattern="old"),),
                    replies=("old reply",),
                ),
            )
        )
    )
    module.default_trigger_reply_service.cooldown_store.mark("old:user:u1", 60)
    monkeypatch.setattr(
        module,
        "trigger_rules_file_paths",
        lambda _config: (rules_path,),
    )

    _count, errors = module.reload_trigger_rules(TriggerReplyConfig())

    assert errors == ()
    assert module.default_rule_set_cache.ruleset.entries[0].id == "new"
    assert not module.default_trigger_reply_service.cooldown_store.is_active(
        "old:user:u1"
    )


def test_reload_function_preserves_active_ruleset_when_file_is_invalid(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text("[[entries]\n", encoding="utf-8")
    module.default_rule_set_cache.set(
        TriggerRuleSet(
            entries=(
                _entry(
                    "old",
                    matches=(TriggerMatch(type="full", pattern="old"),),
                    replies=("old reply",),
                ),
            )
        )
    )
    monkeypatch.setattr(
        module,
        "trigger_rules_file_paths",
        lambda _config: (rules_path,),
    )

    _count, errors = module.reload_trigger_rules(TriggerReplyConfig())

    assert errors
    assert module.default_rule_set_cache.ruleset.entries[0].id == "old"


@pytest.mark.anyio
async def test_message_matcher_sends_and_stops_after_configured_reply(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    propagated: list[str] = []
    _install_rules(
        module,
        monkeypatch,
        stop_propagation_on_match=True,
        entries=(
            _entry(
                "help",
                matches=(TriggerMatch(type="full", pattern="test帮助"),),
                replies=("命中 {user_id}",),
            ),
        ),
    )
    sentinel = on_message(priority=20, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._message, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(user_id="20000", message=fake_message("test帮助"))
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._message)
            ctx.should_pass_rule(module._message)
            ctx.should_call_send(event, "命中 20000", result=None)
    finally:
        sentinel.destroy()

    assert propagated == []


@pytest.mark.anyio
async def test_message_rule_reserves_cooldown_before_handler_delivery(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    _install_rules(
        module,
        monkeypatch,
        entries=(
            TriggerEntry(
                id="cooldown",
                cooldown=TriggerCooldown(seconds=10, scope="user"),
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=(TriggerReply(text="pong"),),
            ),
        ),
    )

    async with app.test_api() as ctx:
        bot = _onebot_bot(ctx)

    event = make_fake_event(message=fake_message("ping"))
    state: dict[str, object] = {}

    await module._is_trigger_message(bot, event, state)
    second_result = module._evaluate_message(bot, event, TriggerReplyConfig())

    assert second_result.decisions == ()


@pytest.mark.anyio
async def test_message_send_failure_releases_reserved_cooldown(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    _install_rules(
        module,
        monkeypatch,
        entries=(
            TriggerEntry(
                id="cooldown",
                cooldown=TriggerCooldown(seconds=10, scope="user"),
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=(TriggerReply(text="pong"),),
            ),
        ),
    )

    async with app.test_matcher(module._message) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(message=fake_message("ping"))
        ctx.receive_event(bot, event)
        ctx.should_pass_permission(module._message)
        ctx.should_pass_rule(module._message)
        ctx.should_call_send(event, "pong", exception=RuntimeError("send failed"))

    retry_result = module._evaluate_message(bot, event, TriggerReplyConfig())
    assert retry_result.should_reply


@pytest.mark.anyio
async def test_message_matcher_keeps_propagation_when_config_allows_it(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    propagated: list[str] = []
    _install_rules(
        module,
        monkeypatch,
        stop_propagation_on_match=False,
        entries=(
            _entry(
                "first",
                priority=1,
                block=False,
                matches=(TriggerMatch(type="start", pattern="test"),),
                replies=("first",),
            ),
            _entry(
                "second",
                priority=2,
                matches=(TriggerMatch(type="fuzzy", pattern="help"),),
                replies=("second",),
            ),
        ),
    )
    sentinel = on_message(priority=20, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._message, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(message=fake_message("test help"))
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._message)
            ctx.should_pass_rule(module._message)
            ctx.should_call_send(event, "first", result=None)
            ctx.should_call_send(event, "second", result=None)
    finally:
        sentinel.destroy()

    assert propagated == ["ran"]


@pytest.mark.anyio
async def test_message_matcher_stops_after_partial_send_success(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    propagated: list[str] = []
    _install_rules(
        module,
        monkeypatch,
        stop_propagation_on_match=True,
        entries=(
            _entry(
                "first",
                priority=1,
                block=False,
                matches=(TriggerMatch(type="start", pattern="test"),),
                replies=("first",),
            ),
            _entry(
                "second",
                priority=2,
                matches=(TriggerMatch(type="fuzzy", pattern="help"),),
                replies=("second",),
            ),
        ),
    )
    sentinel = on_message(priority=20, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._message, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(message=fake_message("test help"))
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._message)
            ctx.should_pass_rule(module._message)
            ctx.should_call_send(event, "first", result=None)
            ctx.should_call_send(event, "second", exception=RuntimeError("send failed"))
    finally:
        sentinel.destroy()

    assert propagated == []


@pytest.mark.anyio
async def test_non_matching_message_passes_through_without_reply(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    propagated: list[str] = []
    _install_rules(
        module,
        monkeypatch,
        entries=(
            _entry(
                "help",
                matches=(TriggerMatch(type="full", pattern="test帮助"),),
                replies=("unused",),
            ),
        ),
    )
    sentinel = on_message(priority=20, block=False)

    @sentinel.handle()
    async def _record() -> None:
        propagated.append("ran")

    try:
        async with app.test_matcher([module._message, sentinel]) as ctx:
            bot = _onebot_bot(ctx)
            event = make_fake_event(message=fake_message("普通消息"))
            ctx.receive_event(bot, event)
            ctx.should_pass_permission(module._message)
            ctx.should_not_pass_rule(module._message)
    finally:
        sentinel.destroy()

    assert propagated == ["ran"]


@pytest.mark.anyio
async def test_poke_matcher_sends_via_provider_and_stops(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    _install_rules(
        module,
        monkeypatch,
        entries=(
            _entry(
                "poke",
                matches=(TriggerMatch(type="poke", to_me=True),),
                replies=("别戳 {target_id}",),
            ),
        ),
    )

    async with app.test_matcher(module._notice) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            event_type="notice",
            user_id="20000",
            group_id="30000",
            notice_type="notify",
            sub_type="poke",
            target_id="10000",
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_pass_rule()
        ctx.should_call_api(
            "send_msg",
            {
                "message": "别戳 10000",
                "group_id": 30000,
                "message_type": "group",
            },
            result=None,
        )


@pytest.mark.anyio
async def test_unsupported_notice_fails_closed(
    app: App,
    monkeypatch: MonkeyPatch,
) -> None:
    module = import_fresh_plugin("apeiria.builtin_plugins.trigger_reply")
    _install_rules(
        module,
        monkeypatch,
        entries=(
            _entry(
                "poke",
                matches=(TriggerMatch(type="poke", to_me=True),),
                replies=("unused",),
            ),
        ),
    )

    async with app.test_matcher(module._notice) as ctx:
        bot = _onebot_bot(ctx)
        event = make_fake_event(
            event_type="notice",
            notice_type="group_recall",
            sub_type="poke",
            target_id="10000",
        )
        ctx.receive_event(bot, event)
        ctx.should_pass_permission()
        ctx.should_not_pass_rule()


def _install_rules(
    module: Any,
    monkeypatch: MonkeyPatch,
    *,
    entries: tuple[TriggerEntry, ...],
    stop_propagation_on_match: bool = True,
) -> None:
    ruleset = TriggerRuleSet(
        entries=tuple(sorted(entries, key=lambda item: item.priority))
    )
    monkeypatch.setattr(
        module,
        "get_trigger_reply_config",
        lambda: TriggerReplyConfig(
            stop_propagation_on_match=stop_propagation_on_match,
        ),
    )
    monkeypatch.setattr(module, "_ensure_rules_loaded", lambda _config: None)
    module.default_rule_set_cache.set(ruleset)
    monkeypatch.setattr(
        module,
        "default_trigger_reply_service",
        TriggerReplyService(
            cooldown_store=TriggerReplyCooldownStore(),
            reply_choice=lambda values: values[0],
        ),
    )


def _entry(
    entry_id: str,
    *,
    priority: int = 1,
    block: bool = True,
    matches: tuple[TriggerMatch, ...],
    replies: tuple[str, ...],
) -> TriggerEntry:
    return TriggerEntry(
        id=entry_id,
        priority=priority,
        block=block,
        matches=matches,
        replies=tuple(TriggerReply(text=reply) for reply in replies),
    )
