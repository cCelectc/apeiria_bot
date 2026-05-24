from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

import apeiria.builtin_plugins.trigger_reply.service as trigger_reply_service_module
from apeiria.builtin_plugins.trigger_reply.config import (
    DEFAULT_RULES_FILE,
    normalize_trigger_reply_config,
)
from apeiria.builtin_plugins.trigger_reply.loader import load_trigger_rule_set
from apeiria.builtin_plugins.trigger_reply.models import (
    TriggerCooldown,
    TriggerEntry,
    TriggerFilter,
    TriggerInput,
    TriggerMatch,
    TriggerReply,
    TriggerRuleSet,
    TriggerSceneFilter,
)
from apeiria.builtin_plugins.trigger_reply.providers import (
    NoneBotMessageInputProvider,
    OneBotV11PokeInputProvider,
)
from apeiria.builtin_plugins.trigger_reply.service import (
    TriggerReplyCooldownStore,
    TriggerReplyService,
)
from tests.plugins.nonebot_helpers import fake_message, make_fake_event

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_trigger_reply_config_normalizes_bounded_values() -> None:
    normalized = normalize_trigger_reply_config(
        {
            "enabled": "off",
            "priority": "0",
            "stop_propagation_on_match": "no",
            "rules_file": "../escape.toml",
            "debug": "yes",
        }
    )

    assert normalized == {
        "enabled": False,
        "priority": 1,
        "stop_propagation_on_match": False,
        "rules_file": DEFAULT_RULES_FILE,
        "debug": True,
    }


def test_loader_keeps_missing_file_empty_and_invalid_file_inactive(
    tmp_path: Path,
) -> None:
    missing = load_trigger_rule_set(tmp_path / "missing.toml")
    assert missing.status == "missing"
    assert missing.entries == ()

    invalid_path = tmp_path / "rules.toml"
    invalid_path.write_text("[broken\n", encoding="utf-8")

    invalid = load_trigger_rule_set(invalid_path)
    assert invalid.status == "invalid"
    assert invalid.entries == ()
    assert invalid.errors


def test_rules_example_file_loads_without_errors() -> None:
    ruleset = load_trigger_rule_set(
        Path("apeiria/builtin_plugins/trigger_reply/rules.example.toml")
    )

    assert ruleset.status == "active"
    assert ruleset.errors == ()
    assert ruleset.entries


def test_loader_normalizes_entries_and_skips_invalid_definitions(tmp_path: Any) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[valid]
priority = 3
block = false
reply = ["hi {user_id}", "hello"]
matches = [
  { type = "regex", match = "test(?P<name>.+)" },
  { type = "regex", match = "[" },
]

[bounded]
reply = "bounded"
cooldown = nan
type = "full"
match = "bounded"
chance = inf

[invalid]
reply = "unused"
""",
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)
    result = TriggerReplyService(reply_choice=lambda values: values[0]).evaluate(
        TriggerInput(source="message", message_text="test42"),
        ruleset=ruleset,
    )
    bounded_result = TriggerReplyService(
        reply_choice=lambda values: values[0]
    ).evaluate(
        TriggerInput(source="message", message_text="bounded"),
        ruleset=ruleset,
    )

    assert result.decisions[0].reply == "hi "
    assert bounded_result.decisions[0].reply == "bounded"


def test_loader_ignores_entries_array_as_unusable_top_level_entry(
    tmp_path: Path,
) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[[entries]]
id = "legacy"
match = "ping"
reply = "pong"
""",
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)

    assert ruleset.entries == ()


def test_loader_supports_shorthand_message_and_poke_entries(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[test-help]
match = ["test帮助", "test help"]
type = "full"
reply = ["这是 test 帮助", "test 可用命令：..."]

[poke]
event = "qq.poke"
reply = "别戳啦"
chance = 0.5
""",
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)
    service = TriggerReplyService(
        random_draw=lambda: 0.0,
        reply_choice=lambda values: values[0],
    )
    message_result = service.evaluate(
        TriggerInput(source="message", message_text="test help"),
        ruleset=ruleset,
    )
    poke_result = service.evaluate(
        TriggerInput(source="poke", target_id="bot", is_to_me=True),
        ruleset=ruleset,
    )

    assert message_result.decisions[0].reply == "这是 test 帮助"
    assert poke_result.decisions[0].reply == "别戳啦"


def test_loader_preserves_reply_whitespace_and_newlines(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        '''
[newline]
match = "ping"
reply = """

第一行
第二行

"""

[weighted]
match = "weighted"
reply = [
  { text = "  保留空白\\n", weight = 1 },
]
''',
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)
    service = TriggerReplyService(reply_choice=lambda values: values[0])

    newline = service.evaluate(
        TriggerInput(source="message", message_text="ping"),
        ruleset=ruleset,
    )
    weighted = service.evaluate(
        TriggerInput(source="message", message_text="weighted"),
        ruleset=ruleset,
    )

    assert newline.decisions[0].reply == "\n第一行\n第二行\n\n"
    assert weighted.decisions[0].reply == "  保留空白\n"


def test_loader_supports_weighted_replies_scenes_and_scoped_filters(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured_weights: tuple[float, ...] = ()

    def choose_first(
        texts: tuple[str, ...],
        *,
        weights: tuple[float, ...],
        k: int,  # noqa: ARG001
    ) -> list[str]:
        nonlocal captured_weights
        captured_weights = weights
        return [texts[0]]

    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[scoped]
scenes = ["group"]
groups = ["qq:123456"]
users = { mode = "black", values = ["qq:999"] }
match = "菜单"
reply = [
  { text = "常用菜单", weight = 5 },
  { text = "备用菜单", weight = 1 },
]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(trigger_reply_service_module, "choices", choose_first)

    ruleset = load_trigger_rule_set(rules_path)
    service = TriggerReplyService()
    allowed = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="100",
            group_id="123456",
            message_text="菜单",
        ),
        ruleset=ruleset,
    )
    blocked_user = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="999",
            group_id="123456",
            message_text="菜单",
        ),
        ruleset=ruleset,
    )
    private = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="100",
            message_text="菜单",
        ),
        ruleset=ruleset,
    )

    assert allowed.decisions[0].reply == "常用菜单"
    assert captured_weights == (5.0, 1.0)
    assert blocked_user.decisions == ()
    assert private.decisions == ()


def test_loader_keeps_explicit_invalid_filters_closed(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[empty-white-filter]
groups = []
match = "菜单"
reply = "allowed"

[bad-scenes]
scenes = ["channel"]
match = "菜单"
reply = "unused"

[bad-groups]
groups = ["123456"]
match = "菜单"
reply = "unused"
""",
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)

    result = TriggerReplyService(reply_choice=lambda values: values[0]).evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            group_id="123456",
            message_text="菜单",
        ),
        ruleset=ruleset,
    )
    assert [decision.entry.id for decision in result.decisions] == [
        "empty-white-filter"
    ]
    assert "bad-scenes: scenes contains unsupported value: channel" in ruleset.errors
    assert (
        "bad-groups: groups contains unsupported scoped value: 123456" in ruleset.errors
    )


def test_loader_reports_invalid_match_type_and_filter_mode(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.toml"
    rules_path.write_text(
        """
[bad-type]
type = "glob"
match = "ping"
reply = "unused"

[bad-filter-mode]
users = { mode = "gray", values = ["qq:100"] }
match = "ping"
reply = "unused"
""",
        encoding="utf-8",
    )

    ruleset = load_trigger_rule_set(rules_path)

    result = TriggerReplyService(reply_choice=lambda values: values[0]).evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="100",
            message_text="ping",
        ),
        ruleset=ruleset,
    )

    assert result.decisions == ()
    assert any("unsupported match type: glob" in error for error in ruleset.errors)
    assert (
        "bad-filter-mode: users contains unsupported filter mode: gray"
        in ruleset.errors
    )


def test_message_provider_uses_channel_scope_when_group_id_is_absent() -> None:
    provider = NoneBotMessageInputProvider()
    bot = _FakeBot(adapter_name="Discord", self_id="bot")
    event = make_fake_event(
        message=fake_message("ping"),
        group_id=None,
        guild_id="guild",
        channel_id="channel",
    )

    trigger = provider.normalize(cast("Any", bot), event)

    assert trigger is not None
    assert trigger.group_id == "guild/channel"
    assert trigger.scoped_group_id == "discord:guild/channel"


def test_service_matches_message_modes_filters_order_and_placeholders() -> None:
    trigger = TriggerInput(
        source="message",
        platform="qq",
        bot_id="bot-1",
        user_id="u1",
        group_id="g1",
        message_id="m1",
        message_text="test帮助",
        plaintext="test帮助",
    )
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "later",
                matches=(TriggerMatch(type="fuzzy", pattern="test"),),
                replies=("later",),
                options=_EntryOptions(priority=20),
            ),
            _entry(
                "first",
                matches=(
                    TriggerMatch(type="full", pattern="test help"),
                    TriggerMatch(type="start", pattern="test"),
                ),
                replies=("first {user_id} {group_id} {message} {trigger}",),
                options=_EntryOptions(
                    priority=10,
                    block=False,
                    groups=TriggerFilter(mode="white", values=frozenset({"qq:g1"})),
                ),
            ),
            _entry(
                "excluded",
                matches=(TriggerMatch(type="fuzzy", pattern="test"),),
                replies=("excluded",),
                options=_EntryOptions(
                    priority=1,
                    users=TriggerFilter(mode="black", values=frozenset({"qq:u1"})),
                ),
            ),
        )
    )

    result = TriggerReplyService(reply_choice=lambda values: values[0]).evaluate(
        trigger,
        ruleset=ruleset,
    )

    assert [decision.entry.id for decision in result.decisions] == ["first", "later"]
    assert result.decisions[0].reply == "first u1 g1 test帮助 test"
    assert result.decisions[1].reply == "later"


def test_service_message_to_me_filter_requires_targeted_message() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "to-me",
                matches=(TriggerMatch(type="full", pattern="ping", to_me=True),),
                replies=("pong",),
            ),
        )
    )

    untargeted = service.evaluate(
        TriggerInput(source="message", message_text="ping", is_to_me=False),
        ruleset=ruleset,
    )
    targeted = service.evaluate(
        TriggerInput(source="message", message_text="ping", is_to_me=True),
        ruleset=ruleset,
    )

    assert untargeted.decisions == ()
    assert [decision.reply for decision in targeted.decisions] == ["pong"]


def test_service_supports_regex_variables_and_plaintext_matching() -> None:
    trigger = TriggerInput(
        source="message",
        user_id="u1",
        message_text="[fake:mention] 帮助42",
        plaintext="帮助42",
    )
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "regex",
                matches=(
                    TriggerMatch(
                        type="regex",
                        pattern=r"帮助(?P<num>\d+)",
                        compiled_pattern=__import__("re").compile(r"帮助(?P<num>\d+)"),
                    ),
                ),
                replies=("hit {v0} {num} {unknown}",),
            ),
        )
    )

    result = TriggerReplyService(reply_choice=lambda values: values[0]).evaluate(
        trigger,
        ruleset=ruleset,
    )

    assert result.decisions[0].reply == "hit 帮助42 42 {unknown}"


def test_service_keeps_invalid_template_literal() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "template",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("{message!x}",),
            ),
        )
    )

    result = service.evaluate(
        TriggerInput(source="message", message_text="ping"),
        ruleset=ruleset,
    )

    assert result.decisions[0].reply == "{message!x}"


def test_service_chance_and_cooldown_suppress_replies() -> None:
    clock = _Clock()
    service = TriggerReplyService(
        cooldown_store=TriggerReplyCooldownStore(clock=clock),
        random_draw=lambda: 0.5,
        reply_choice=lambda values: values[0],
    )
    trigger = TriggerInput(source="message", user_id="u1", message_text="ping")
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "chance",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("never",),
                options=_EntryOptions(priority=1, block=False, chance=0.1),
            ),
            _entry(
                "cooldown",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("once",),
                options=_EntryOptions(
                    priority=2,
                    cooldown=TriggerCooldown(seconds=10, scope="user"),
                ),
            ),
        )
    )

    first = service.evaluate(trigger, ruleset=ruleset)
    service.commit_cooldowns(first)
    second = service.evaluate(trigger, ruleset=ruleset)
    clock.now = 11
    third = service.evaluate(trigger, ruleset=ruleset)
    service.commit_cooldowns(third)

    assert [decision.reply for decision in first.decisions] == ["once"]
    assert second.decisions == ()
    assert [decision.reply for decision in third.decisions] == ["once"]


def test_service_chance_zero_never_replies_even_with_zero_draw() -> None:
    service = TriggerReplyService(
        random_draw=lambda: 0.0,
        reply_choice=lambda values: values[0],
    )
    trigger = TriggerInput(source="message", message_text="ping")
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "zero",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("never",),
                options=_EntryOptions(chance=0.0),
            ),
        )
    )

    result = service.evaluate(trigger, ruleset=ruleset)

    assert result.decisions == ()


def test_service_filters_scenes_scoped_ids_and_wildcards() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "qq-groups",
                matches=(TriggerMatch(type="full", pattern="menu"),),
                replies=("group menu",),
                options=_EntryOptions(
                    block=False,
                    scenes=TriggerSceneFilter(values=frozenset({"group"})),
                    groups=TriggerFilter(mode="white", values=frozenset({"qq:*"})),
                ),
            ),
            _entry(
                "private-only",
                matches=(TriggerMatch(type="full", pattern="menu"),),
                replies=("private menu",),
                options=_EntryOptions(
                    priority=2,
                    scenes=TriggerSceneFilter(values=frozenset({"private"})),
                    users=TriggerFilter(mode="white", values=frozenset({"qq:*"})),
                ),
            ),
        )
    )

    group_result = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="u1",
            group_id="g1",
            message_text="menu",
        ),
        ruleset=ruleset,
    )
    private_result = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="u1",
            message_text="menu",
        ),
        ruleset=ruleset,
    )

    assert [decision.reply for decision in group_result.decisions] == ["group menu"]
    assert [decision.reply for decision in private_result.decisions] == ["private menu"]


def test_service_renders_text_and_rest_variables() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "repeat",
                matches=(TriggerMatch(type="start", pattern="复读"),),
                replies=("{text}|{rest}",),
            ),
        )
    )

    result = service.evaluate(
        TriggerInput(
            source="message",
            message_text="[fake:mention] 复读 hello",
            plaintext="复读 hello",
        ),
        ruleset=ruleset,
    )

    assert result.decisions[0].reply == "复读 hello|hello"


def test_service_evaluation_does_not_commit_cooldown_until_success() -> None:
    service = TriggerReplyService(
        reply_choice=lambda values: values[0],
    )
    trigger = TriggerInput(source="message", user_id="u1", message_text="ping")
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "cooldown",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("once",),
                options=_EntryOptions(
                    cooldown=TriggerCooldown(seconds=10, scope="user"),
                ),
            ),
        )
    )

    second = service.evaluate(trigger, ruleset=ruleset)
    service.commit_cooldowns(second)
    third = service.evaluate(trigger, ruleset=ruleset)

    assert second.should_reply
    assert third.decisions == ()


def test_service_can_reserve_and_release_cooldowns_before_delivery() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    trigger = TriggerInput(source="message", user_id="u1", message_text="ping")
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "cooldown",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("once",),
                options=_EntryOptions(
                    cooldown=TriggerCooldown(seconds=10, scope="user"),
                ),
            ),
        )
    )

    first = service.evaluate(trigger, ruleset=ruleset)
    service.reserve_cooldowns(first)
    blocked = service.evaluate(trigger, ruleset=ruleset)
    service.release_cooldowns(first)
    after_release = service.evaluate(trigger, ruleset=ruleset)
    service.reserve_cooldowns(after_release)
    service.commit_cooldowns(after_release)
    after_commit = service.evaluate(trigger, ruleset=ruleset)

    assert blocked.decisions == ()
    assert after_release.should_reply
    assert after_commit.decisions == ()


def test_service_cooldown_scopes_include_platform_when_available() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "cooldown",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("once",),
                options=_EntryOptions(
                    cooldown=TriggerCooldown(seconds=10, scope="user"),
                ),
            ),
        )
    )

    qq = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="100",
            message_text="ping",
        ),
        ruleset=ruleset,
    )
    service.commit_cooldowns(qq)
    other_platform = service.evaluate(
        TriggerInput(
            source="message",
            platform="other",
            user_id="100",
            message_text="ping",
        ),
        ruleset=ruleset,
    )
    same_platform = service.evaluate(
        TriggerInput(
            source="message",
            platform="qq",
            user_id="100",
            message_text="ping",
        ),
        ruleset=ruleset,
    )

    assert other_platform.should_reply
    assert same_platform.decisions == ()


def test_service_matches_poke_with_to_me_semantics() -> None:
    service = TriggerReplyService(reply_choice=lambda values: values[0])
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "poke",
                matches=(TriggerMatch(type="poke", to_me=True),),
                replies=("poke {target_id}",),
            ),
        )
    )

    assert not service.evaluate(
        TriggerInput(source="poke", target_id="someone", is_to_me=False),
        ruleset=ruleset,
    ).should_reply
    assert (
        service.evaluate(
            TriggerInput(source="poke", target_id="bot", is_to_me=True),
            ruleset=ruleset,
        )
        .decisions[0]
        .reply
        == "poke bot"
    )


@pytest.mark.anyio
async def test_poke_provider_delivers_group_and_private_replies() -> None:
    provider = OneBotV11PokeInputProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")

    await provider.send_reply(
        cast("Any", bot),
        TriggerInput(
            source="poke",
            user_id="20000",
            group_id="30000",
            target_id="10000",
        ),
        message="group reply",
    )
    await provider.send_reply(
        cast("Any", bot),
        TriggerInput(source="poke", user_id="20000", target_id="10000"),
        message="private reply",
    )

    assert bot.calls == [
        (
            "send_msg",
            {
                "message": "group reply",
                "group_id": 30000,
                "message_type": "group",
            },
        ),
        (
            "send_msg",
            {
                "message": "private reply",
                "user_id": 20000,
                "message_type": "private",
            },
        ),
    ]


def test_provider_supports_platform_aliases_for_scoped_filters() -> None:
    message_provider = NoneBotMessageInputProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="bot")
    event = make_fake_event(message=fake_message("ping"))

    trigger = message_provider.normalize(cast("Any", bot), event)
    ruleset = TriggerRuleSet(
        entries=(
            _entry(
                "qq",
                matches=(TriggerMatch(type="full", pattern="ping"),),
                replies=("pong",),
                options=_EntryOptions(
                    users=TriggerFilter(
                        mode="white",
                        values=frozenset({"qq:20000"}),
                    ),
                ),
            ),
        )
    )

    assert trigger is not None
    assert (
        TriggerReplyService(reply_choice=lambda values: values[0])
        .evaluate(trigger, ruleset=ruleset)
        .should_reply
    )


def _entry(
    entry_id: str,
    *,
    matches: tuple[TriggerMatch, ...],
    replies: tuple[str, ...],
    options: _EntryOptions | None = None,
) -> TriggerEntry:
    resolved_options = options or _EntryOptions()
    return TriggerEntry(
        id=entry_id,
        priority=resolved_options.priority,
        block=resolved_options.block,
        chance=resolved_options.chance,
        scenes=resolved_options.scenes,
        groups=resolved_options.groups,
        users=resolved_options.users,
        cooldown=resolved_options.cooldown,
        matches=matches,
        replies=tuple(TriggerReply(text=reply) for reply in replies),
    )


@dataclass(frozen=True, slots=True)
class _EntryOptions:
    priority: int = 1
    block: bool = True
    chance: float = 1.0
    scenes: TriggerSceneFilter = field(default_factory=TriggerSceneFilter)
    groups: TriggerFilter = field(default_factory=TriggerFilter)
    users: TriggerFilter = field(default_factory=TriggerFilter)
    cooldown: TriggerCooldown | None = None


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _FakeBot:
    def __init__(self, *, adapter_name: str, self_id: str) -> None:
        self.type = adapter_name
        self.self_id = self_id
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_api(self, api: str, **data: object) -> object:
        self.calls.append((api, data))
        return {"status": "ok"}
