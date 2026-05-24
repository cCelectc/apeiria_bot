from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any, cast

from apeiria.ai.contributions import ai_contributions
from apeiria.ai.plugin_api import live_platform_context as get_plugin_live_context
from apeiria.ai.skills.loader import load_skills_from_sources
from apeiria.ai.skills.runtime import AISkillRuntime
from apeiria.ai.tools.exposure import create_tool_exposure_plan
from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolExecutionContext,
    AIToolLevel,
    AIToolPolicy,
)
from apeiria.ai.tools.policy import (
    AIToolSceneContext,
    evaluate_tool_policy,
    resolve_default_tool_policy,
)
from apeiria.bot.live_context import live_platform_context
from apeiria.builtin_plugins.qq_tools import tools
from apeiria.builtin_plugins.qq_tools.providers import (
    OneBotV11QQToolProvider,
    QQActionResult,
    QQGroupMember,
    QQGroupMemberLookupResult,
    QQMentionFragmentResult,
    QQToolProviderRegistry,
)


def test_qq_tools_contribute_only_decorated_ai_tools() -> None:
    importlib.import_module("apeiria.builtin_plugins.qq_tools")

    snapshot = ai_contributions.snapshot()
    qq_tool_names = sorted(
        contribution.tool.name
        for contribution in snapshot.tools
        if contribution.tool.name.startswith(("qq.", "onebot."))
    )

    assert qq_tool_names == [
        "qq.get_group_members",
        "qq.mention_user",
        "qq.poke",
        "qq.react_to_message",
    ]
    assert _tool_definition(tools.get_group_members).origin == "plugin"
    assert _tool_definition(tools.mention_user).origin == "plugin"
    assert _tool_definition(tools.poke).origin == "plugin"
    assert _tool_definition(tools.react_to_message).origin == "plugin"


def test_qq_tools_have_write_level_and_narrow_schemas() -> None:
    lookup_definition = _tool_definition(tools.get_group_members)
    mention_definition = _tool_definition(tools.mention_user)
    poke_definition = _tool_definition(tools.poke)
    reaction_definition = _tool_definition(tools.react_to_message)

    assert lookup_definition.required_level is AIToolLevel.WRITE
    assert lookup_definition.input_schema == {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Keyword",
                "default": "",
            }
        },
        "additionalProperties": False,
    }
    assert mention_definition.required_level is AIToolLevel.WRITE
    assert mention_definition.input_schema == {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "User id",
            }
        },
        "additionalProperties": False,
        "required": ["user_id"],
    }
    assert poke_definition.required_level is AIToolLevel.WRITE
    assert poke_definition.input_schema == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert reaction_definition.required_level is AIToolLevel.WRITE
    assert reaction_definition.input_schema == {
        "type": "object",
        "properties": {
            "reaction": {
                "type": "string",
                "description": "Reaction",
                "enum": ["like"],
                "default": "like",
            }
        },
        "additionalProperties": False,
    }


def test_qq_tools_skill_is_contributed_and_parseable() -> None:
    module = importlib.import_module("apeiria.builtin_plugins.qq_tools")
    skill_path = Path(module.__file__).parent / "skills" / "qq-tools" / "SKILL.md"

    snapshot = ai_contributions.snapshot()
    assert any(source.path == skill_path for source in snapshot.skill_sources)

    loaded = load_skills_from_sources((skill_path,))
    assert len(loaded) == 1
    skill = loaded[0]
    assert skill.skill_name == "qq-tools"
    assert skill.entry_mode == "prompt_only"
    assert skill.tools == (
        "qq.get_group_members",
        "qq.mention_user",
        "qq.poke",
        "qq.react_to_message",
    )

    runtime = AISkillRuntime()
    runtime.register_file_skills(loaded)
    activation = runtime.activate_skill_explicit("qq-tools")
    assert activation is not None
    assert activation.tools == (
        "qq.get_group_members",
        "qq.mention_user",
        "qq.poke",
        "qq.react_to_message",
    )


def test_live_platform_context_is_available_and_resets() -> None:
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", message_id="123")

    assert get_plugin_live_context() is None
    with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
        live = get_plugin_live_context()
        assert live is not None
        assert live.bot is bot
        assert live.event is event
    assert get_plugin_live_context() is None


def test_missing_live_context_returns_not_ready() -> None:
    async def scenario() -> None:
        result = await tools.poke(context=_execution_context())

        assert result.status == "not_ready"
        assert result.output_payload == {
            "status": "not_ready",
            "reason": "runtime_missing_capability",
        }

    asyncio.run(scenario())


def test_qq_provider_registry_resolves_supported_provider() -> None:
    registry = QQToolProviderRegistry(providers=(OneBotV11QQToolProvider(),))

    assert isinstance(
        registry.resolve(
            cast("Any", _FakeBot(adapter_name="OneBot V11", self_id="10000")),
            cast("Any", _FakeEvent(user_id="20000", message_id="123")),
        ),
        OneBotV11QQToolProvider,
    )
    assert (
        registry.resolve(
            cast("Any", _FakeBot(adapter_name="Console", self_id="10000")),
            cast("Any", _FakeEvent(user_id="20000", message_id="123")),
        )
        is None
    )


def test_onebot_poke_current_actor_calls_bounded_api() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.poke_current_actor(cast("Any", bot), cast("Any", event))

        assert result == QQActionResult.succeeded()
        assert bot.calls == [
            (
                "send_poke",
                {"user_id": 20000, "group_id": 30000, "target_id": 20000},
            )
        ]

    asyncio.run(scenario())


def test_onebot_poke_requires_resolved_actor() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(message_id="123", raise_user=True)

    async def scenario() -> None:
        result = await provider.poke_current_actor(cast("Any", bot), cast("Any", event))

        assert result.status == "unsupported"
        assert result.reason == "poke_target_unavailable"
        assert bot.calls == []

    asyncio.run(scenario())


def test_onebot_react_to_message_calls_bounded_api() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", message_id="123")

    async def scenario() -> None:
        result = await provider.react_to_message(
            cast("Any", bot),
            cast("Any", event),
            reaction="like",
        )

        assert result == QQActionResult.succeeded()
        assert bot.calls == [
            ("set_msg_emoji_like", {"message_id": 123, "emoji_id": "124"})
        ]

    asyncio.run(scenario())


def test_onebot_reaction_requires_resolved_message() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", raise_message=True)

    async def scenario() -> None:
        result = await provider.react_to_message(
            cast("Any", bot),
            cast("Any", event),
            reaction="like",
        )

        assert result.status == "unsupported"
        assert result.reason == "message_target_unavailable"
        assert bot.calls == []

    asyncio.run(scenario())


def test_onebot_group_member_lookup_calls_bounded_current_group_api() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "get_group_member_list": [
                {
                    "user_id": 20000,
                    "nickname": "Alice",
                    "card": "小爱",
                    "role": "member",
                },
                {
                    "user_id": "20001",
                    "nickname": "Bob",
                    "card": "",
                    "role": "admin",
                },
                {"nickname": "missing id"},
            ]
        },
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(
            cast("Any", bot),
            cast("Any", event),
            keyword="",
        )

        assert result == QQGroupMemberLookupResult(
            status="success",
            group_id="30000",
            members=(
                QQGroupMember(
                    user_id="20000",
                    nickname="Alice",
                    group_card="小爱",
                    role="member",
                ),
                QQGroupMember(
                    user_id="20001",
                    nickname="Bob",
                    group_card="",
                    role="admin",
                ),
            ),
            total_matches=2,
            truncated=False,
        )
        assert [member.to_payload() for member in result.members] == [
            {
                "user_id": "20000",
                "nickname": "Alice",
                "group_card": "小爱",
                "role": "member",
            },
            {
                "user_id": "20001",
                "nickname": "Bob",
                "group_card": "",
                "role": "admin",
            },
        ]
        assert bot.calls == [("get_group_member_list", {"group_id": 30000})]

    asyncio.run(scenario())


def test_onebot_group_member_lookup_filters_by_keyword() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "get_group_member_list": [
                {"user_id": "20000", "nickname": "Alice", "card": "小爱"},
                {"user_id": "20001", "nickname": "Bob", "card": "项目负责人"},
            ]
        },
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(
            cast("Any", bot),
            cast("Any", event),
            keyword="负责",
        )

        assert result.status == "success"
        assert result.total_matches == 1
        assert result.truncated is False
        assert [member.user_id for member in result.members] == ["20001"]

    asyncio.run(scenario())


def test_onebot_group_member_lookup_caps_results() -> None:
    result_limit = 20
    total_members = result_limit + 1
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "get_group_member_list": [
                {"user_id": str(20000 + index), "nickname": f"Member {index}"}
                for index in range(total_members)
            ]
        },
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(
            cast("Any", bot),
            cast("Any", event),
            limit=50,
        )

        assert result.status == "success"
        assert len(result.members) == result_limit
        assert result.total_matches == total_members
        assert result.truncated is True

    asyncio.run(scenario())


def test_onebot_group_member_lookup_requires_group_context() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(cast("Any", bot), cast("Any", event))

        assert result.status == "unsupported"
        assert result.reason == "group_context_unavailable"
        assert bot.calls == []

    asyncio.run(scenario())


def test_onebot_group_member_lookup_platform_failure_is_bounded() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        fail_apis={"get_group_member_list"},
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(cast("Any", bot), cast("Any", event))

        assert result.status == "failed"
        assert result.reason == "platform_operation_failed"
        assert bot.calls == [("get_group_member_list", {"group_id": 30000})]

    asyncio.run(scenario())


def test_onebot_group_member_lookup_missing_api_is_not_ready() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBotWithoutCallAPI(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(cast("Any", bot), cast("Any", event))

        assert result.status == "unsupported"
        assert result.reason == "platform_api_unavailable"

    asyncio.run(scenario())


def test_onebot_group_member_lookup_invalid_response_is_bounded() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={"get_group_member_list": {"unexpected": "shape"}},
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.get_group_members(cast("Any", bot), cast("Any", event))

        assert result.status == "failed"
        assert result.reason == "platform_response_invalid"

    asyncio.run(scenario())


def test_onebot_mention_user_returns_fragment_without_sending() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        result = await provider.mention_user(
            cast("Any", bot),
            cast("Any", event),
            user_id=" 20001 ",
        )

        assert result == QQMentionFragmentResult(
            status="success",
            user_id="20001",
            mention="[CQ:at,qq=20001]",
        )
        assert bot.calls == []
        assert bot.sent == []

    asyncio.run(scenario())


def test_onebot_mention_user_rejects_invalid_ids() -> None:
    provider = OneBotV11QQToolProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        for user_id in ("all", "[CQ:at,qq=123]", "abc", "0", "123 456"):
            result = await provider.mention_user(
                cast("Any", bot),
                cast("Any", event),
                user_id=user_id,
            )
            assert result.status == "unsupported"
            assert result.reason == "invalid_user_id"

        assert bot.calls == []
        assert bot.sent == []

    asyncio.run(scenario())


def test_provider_failure_becomes_bounded_tool_error() -> None:
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        fail_apis={"set_msg_emoji_like"},
    )
    event = _FakeEvent(user_id="20000", message_id="123")

    async def scenario() -> None:
        with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
            result = await tools.react_to_message(context=_execution_context())

        assert result.status == "error"
        assert result.output_payload == {
            "status": "failed",
            "reason": "platform_operation_failed",
        }
        assert "_FakePlatformError" not in result.summary
        assert bot.calls == [
            ("set_msg_emoji_like", {"message_id": 123, "emoji_id": "124"})
        ]

    asyncio.run(scenario())


def test_mention_tool_returns_payload_fragment() -> None:
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
            result = await tools.mention_user(
                "20001",
                context=_execution_context(),
            )

        assert result.status == "success"
        assert result.output_payload == {
            "status": "success",
            "user_id": "20001",
            "mention": "[CQ:at,qq=20001]",
        }
        assert "[CQ:at,qq=20001]" in result.summary
        assert "user_id=20001" in result.summary
        assert bot.calls == []
        assert bot.sent == []

    asyncio.run(scenario())


def test_mention_tool_rejects_invalid_user_id_without_sending() -> None:
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
            result = await tools.mention_user(
                "all",
                context=_execution_context(),
            )

        assert result.status == "not_ready"
        assert result.output_payload == {
            "status": "unsupported",
            "user_id": None,
            "mention": None,
            "reason": "invalid_user_id",
        }
        assert bot.calls == []
        assert bot.sent == []

    asyncio.run(scenario())


def test_mention_tool_unsupported_adapter_returns_not_ready() -> None:
    bot = _FakeBot(adapter_name="Console", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
            result = await tools.mention_user(
                "20001",
                context=_execution_context(),
            )

        assert result.status == "not_ready"
        assert result.output_payload == {
            "status": "not_ready",
            "reason": "unsupported_adapter",
        }
        assert bot.calls == []
        assert bot.sent == []

    asyncio.run(scenario())


def test_group_member_lookup_tool_returns_bounded_payload() -> None:
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "get_group_member_list": [
                {"user_id": "20000", "nickname": "Alice", "card": "小爱"},
                {"user_id": "20001", "nickname": "Bob", "card": "项目负责人"},
            ]
        },
    )
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="123")

    async def scenario() -> None:
        with live_platform_context(bot=cast("Any", bot), event=cast("Any", event)):
            result = await tools.get_group_members(
                "负责",
                context=_execution_context(),
            )

        assert result.status == "success"
        assert result.output_payload == {
            "status": "success",
            "group_id": "30000",
            "count": 1,
            "total_matches": 1,
            "truncated": False,
            "members": [
                {
                    "user_id": "20001",
                    "nickname": "Bob",
                    "group_card": "项目负责人",
                    "role": "member",
                }
            ],
        }
        assert "user_id=20001" in result.summary
        assert "nickname=Bob" in result.summary
        assert "group_card=项目负责人" in result.summary
        assert bot.calls == [("get_group_member_list", {"group_id": 30000})]

    asyncio.run(scenario())


def test_qq_tools_are_denied_below_write_and_hidden_in_default_group() -> None:
    qq_definitions = (
        _tool_definition(tools.get_group_members),
        _tool_definition(tools.mention_user),
        _tool_definition(tools.poke),
        _tool_definition(tools.react_to_message),
    )

    for tool in qq_definitions:
        read_decision = evaluate_tool_policy(
            tool,
            AIToolPolicy(allowed_level=AIToolLevel.READ),
        )
        assert not read_decision.allowed
        assert read_decision.reason == "requires write, scene allows read"

    default_group_policy = resolve_default_tool_policy(
        AIToolSceneContext(scope_type="group", is_tome=False)
    )
    default_group_plan = create_tool_exposure_plan(
        tools=qq_definitions,
        policy=default_group_policy,
        model_supports_tools=True,
    )
    assert default_group_policy.allowed_level is AIToolLevel.NONE
    assert default_group_plan.visible_tool_names == ()
    assert set(default_group_plan.denied_reasons) == {
        "qq.get_group_members",
        "qq.mention_user",
        "qq.poke",
        "qq.react_to_message",
    }

    explicit_write_plan = create_tool_exposure_plan(
        tools=qq_definitions,
        policy=AIToolPolicy(allowed_level=AIToolLevel.WRITE),
        model_supports_tools=True,
    )
    assert explicit_write_plan.visible_tool_names == (
        "qq.get_group_members",
        "qq.mention_user",
        "qq.poke",
        "qq.react_to_message",
    )


def _tool_definition(func: object) -> AIToolDefinition:
    return cast("AIToolDefinition", cast("Any", func).__ai_tool_definition__)


def _execution_context() -> AIToolExecutionContext:
    return AIToolExecutionContext(
        session_id="session-1",
        source_message_id="message-1",
        trace_id="trace-1",
        message_text="hello",
        policy=AIToolPolicy(allowed_level=AIToolLevel.WRITE),
        recalled_memory_ids=(),
        recalled_memory_contents=(),
        relationship_context=None,
        execution_timeout_seconds=None,
    )


class _FakeBot:
    def __init__(
        self,
        *,
        adapter_name: str,
        self_id: str,
        fail_apis: set[str] | None = None,
        api_results: dict[str, object] | None = None,
    ) -> None:
        self.type = adapter_name
        self.self_id = self_id
        self.fail_apis = fail_apis or set()
        self.api_results = api_results or {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.sent: list[tuple[object, object]] = []

    async def call_api(self, api: str, **data: object) -> object:
        self.calls.append((api, data))
        if api in self.fail_apis:
            raise _FakePlatformError
        return self.api_results.get(api, {})

    async def send(self, event: object, message: object) -> None:
        self.sent.append((event, message))


class _FakeBotWithoutCallAPI:
    def __init__(
        self,
        *,
        adapter_name: str,
        self_id: str,
    ) -> None:
        self.type = adapter_name
        self.self_id = self_id


class _FakeEvent:
    def __init__(
        self,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        message_id: str | None = None,
        raise_user: bool = False,
        raise_message: bool = False,
    ) -> None:
        self.user_id = user_id
        self.group_id = group_id
        self.message_id = message_id
        self.raise_user = raise_user
        self.raise_message = raise_message

    def get_user_id(self) -> str:
        if self.raise_user:
            raise _FakeEventError
        return str(self.user_id or "")

    def get_message_id(self) -> str:
        if self.raise_message:
            raise _FakeEventError
        return str(self.message_id or "")


class _FakePlatformError(RuntimeError):
    pass


class _FakeEventError(RuntimeError):
    pass
