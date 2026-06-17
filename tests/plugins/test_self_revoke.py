from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import nonebot

from apeiria.builtin_plugins.self_revoke.config import (
    SelfRevokeConfig,
    normalize_self_revoke_config,
)
from apeiria.builtin_plugins.self_revoke.providers import (
    DiscordSelfRevokeProvider,
    FeishuSelfRevokeProvider,
    OneBotV11SelfRevokeProvider,
    OneBotV12SelfRevokeProvider,
    QQGuildSelfRevokeProvider,
    RevokeActionResult,
    RevokeTarget,
    SatoriSelfRevokeProvider,
    SelfRevokeProviderRegistry,
    TelegramSelfRevokeProvider,
    self_revoke_provider_registry,
)
from apeiria.builtin_plugins.self_revoke.service import (
    handle_self_revoke_event,
    is_revoke_trigger_text,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_self_revoke_config_normalizes_safe_defaults() -> None:
    assert normalize_self_revoke_config(
        {
            "permission": "SUPERUSER",
            "revoke_trigger_message": "yes",
            "feedback": "REACTION",
        }
    ) == {
        "permission": "superuser",
        "revoke_trigger_message": True,
        "feedback": "reaction",
    }
    assert normalize_self_revoke_config(
        {
            "permission": "owner",
            "revoke_trigger_message": "unknown",
            "feedback": "text",
        }
    ) == {
        "permission": "public",
        "revoke_trigger_message": False,
        "feedback": "silent",
    }


def test_self_revoke_trigger_text_matching() -> None:
    assert is_revoke_trigger_text("撤回")
    assert is_revoke_trigger_text(" ReVoKe ")
    assert not is_revoke_trigger_text("请撤回")


def test_providers_revoke_bot_authored_replies_with_platform_payloads() -> None:
    async def scenario() -> None:
        for case in _bot_authored_revoke_cases():
            target = await case.provider.get_reply_target(case.bot, case.event)
            assert target == case.target, case.name
            assert target is not None, case.name
            assert await case.provider.is_bot_authored(
                case.bot,
                case.event,
                target,
            ), case.name

            result = await case.provider.revoke_message(case.bot, case.event, target)
            assert result.success, case.name
            if case.revoke_trigger:
                trigger_result = await case.provider.revoke_trigger_message(
                    case.bot,
                    case.event,
                )
                assert trigger_result.success, case.name
            assert case.bot.calls == case.api_calls, case.name

    asyncio.run(scenario())


def test_providers_reject_non_bot_authored_replies() -> None:
    async def scenario() -> None:
        for case in _non_bot_reply_cases():
            target = await case.provider.get_reply_target(case.bot, case.event)
            assert target is not None, case.name
            assert not await case.provider.is_bot_authored(
                case.bot,
                case.event,
                target,
            ), case.name

    asyncio.run(scenario())


def test_onebot_provider_reaction_is_best_effort() -> None:
    provider = OneBotV11SelfRevokeProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        fail_apis={"set_msg_emoji_like"},
    )
    event = _FakeEvent(
        self_id="10000",
        user_id="20000",
        message_id=123,
        reply=_Reply(message_id=456, user_id="10000"),
    )

    async def scenario() -> None:
        result = await provider.apply_feedback(bot, event, kind="success")

        assert result.status == "failed"
        assert bot.calls == [
            (
                "set_msg_emoji_like",
                {"message_id": 123, "emoji_id": "124"},
            )
        ]

    asyncio.run(scenario())


def test_onebot_v12_provider_requires_consistent_bot_identity() -> None:
    provider = OneBotV12SelfRevokeProvider()
    bot = _FakeBot(adapter_name="OneBot V12", self_id="10000")
    event = _FakeOneBotV12Event(
        self_user_id="10001",
        user_id="20000",
        message_id="trigger-123",
        reply=_OneBotV12Reply(message_id="target-456", user_id="10000"),
    )

    async def scenario() -> None:
        target = await provider.get_reply_target(bot, event)
        assert target is not None
        assert not await provider.is_bot_authored(bot, event, target)

    asyncio.run(scenario())


def test_onebot_v12_provider_reaction_is_unsupported() -> None:
    provider = OneBotV12SelfRevokeProvider()
    bot = _FakeBot(adapter_name="OneBot V12", self_id="10000")
    event = _FakeOneBotV12Event(
        self_user_id="10000",
        user_id="20000",
        message_id="trigger-123",
        reply=_OneBotV12Reply(message_id="target-456", user_id="10000"),
    )

    async def scenario() -> None:
        result = await provider.apply_feedback(bot, event, kind="success")

        assert result.status == "unsupported"
        assert bot.calls == []

    asyncio.run(scenario())


def test_onebot_v11_and_v12_providers_do_not_claim_each_other_events() -> None:
    v11 = OneBotV11SelfRevokeProvider()
    v12 = OneBotV12SelfRevokeProvider()
    v11_bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    v12_bot = _FakeBot(adapter_name="OneBot V12", self_id="10000")
    v11_event = _FakeEvent(
        reply=_Reply(message_id=456, user_id="10000"),
    )
    v12_event = _FakeOneBotV12Event(
        self_user_id="10000",
        user_id="20000",
        message_id="trigger-123",
        reply=_OneBotV12Reply(message_id="target-456", user_id="10000"),
    )

    assert v11.supports(v11_bot, v11_event)
    assert not v11.supports(v12_bot, v12_event)
    assert v12.supports(v12_bot, v12_event)
    assert not v12.supports(v11_bot, v11_event)


def test_default_registry_resolves_onebot_v11_and_v12_events() -> None:
    v11_bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    v12_bot = _FakeBot(adapter_name="OneBot V12", self_id="10000")

    assert isinstance(
        self_revoke_provider_registry.resolve(
            v11_bot,
            _FakeEvent(reply=_Reply(message_id=456, user_id="10000")),
        ),
        OneBotV11SelfRevokeProvider,
    )
    assert isinstance(
        self_revoke_provider_registry.resolve(
            v12_bot,
            _FakeOneBotV12Event(
                self_user_id="10000",
                user_id="20000",
                message_id="trigger-123",
                reply=_OneBotV12Reply(message_id="target-456", user_id="10000"),
            ),
        ),
        OneBotV12SelfRevokeProvider,
    )


def test_feishu_provider_requires_current_app_identity() -> None:
    provider = FeishuSelfRevokeProvider()
    event = _FakeFeishuEvent(
        message_id="trigger-123",
        reply=_FeishuReply(
            message_id="target-456",
            sender_id="app-1",
            sender_id_type="app_id",
        ),
    )

    assert not provider.supports(_FakeBot(adapter_name="Feishu", self_id=""), event)


def test_satori_provider_fetches_missing_reply_author() -> None:
    provider = SatoriSelfRevokeProvider()
    bot = _FakeSatoriBot(self_id="bot-1", fetched_author_id="bot-1")
    event = _FakeSatoriEvent(
        channel_id="channel-1",
        message_id="trigger-123",
        reply=_SatoriReply(message_id="target-456", author_id=None),
    )

    async def scenario() -> None:
        target = await provider.get_reply_target(bot, event)
        assert target == RevokeTarget(message_id="target-456", author_id="bot-1")
        assert await provider.is_bot_authored(bot, event, target)

        result = await provider.revoke_message(bot, event, target)

        assert result.success
        assert bot.calls == [
            (
                "message_get",
                {"channel_id": "channel-1", "message_id": "target-456"},
            ),
            (
                "message_delete",
                {"channel_id": "channel-1", "message_id": "target-456"},
            ),
        ]

    assert provider.supports(bot, event)
    asyncio.run(scenario())


def test_satori_provider_rejects_when_missing_reply_author_cannot_be_fetched() -> None:
    provider = SatoriSelfRevokeProvider()
    bot = _FakeSatoriBot(self_id="bot-1")
    event = _FakeSatoriEvent(
        channel_id="channel-1",
        message_id="trigger-123",
        reply=_SatoriReply(message_id="target-456", author_id=None),
    )

    async def scenario() -> None:
        target = await provider.get_reply_target(bot, event)
        assert target is None
        assert bot.calls == [
            (
                "message_get",
                {"channel_id": "channel-1", "message_id": "target-456"},
            )
        ]

    assert provider.supports(bot, event)
    asyncio.run(scenario())


def test_qq_direct_message_event_is_not_supported() -> None:
    provider = QQGuildSelfRevokeProvider()
    bot = _FakeBot(adapter_name="QQ", self_id="10000")
    event = _FakeChannelEvent(
        adapter_event_type="direct_message_create",
        message_id="trigger-123",
        channel_id="channel-1",
        reply=_FakeMessageGet(message_id="target-456", author_id="10000"),
    )

    assert not provider.supports(bot, event)


def test_optional_provider_registry_resolution() -> None:
    registry = self_revoke_provider_registry

    assert isinstance(
        registry.resolve(
            _FakeBot(adapter_name="Telegram", self_id="10000"),
            _FakeTelegramEvent(
                chat_id=-1001,
                message_id=123,
                reply=_FakeTelegramMessage(message_id=456, from_id="10000"),
            ),
        ),
        TelegramSelfRevokeProvider,
    )
    assert isinstance(
        registry.resolve(
            _FakeBot(adapter_name="Discord", self_id="10000"),
            _FakeChannelEvent(
                adapter_event_type="message_create",
                message_id="trigger-123",
                channel_id="channel-1",
                reply=_FakeMessageGet(message_id="target-456", author_id="10000"),
            ),
        ),
        DiscordSelfRevokeProvider,
    )
    assert isinstance(
        registry.resolve(
            _FakeBot(adapter_name="Feishu", self_id="cli-id"),
            _FakeFeishuEvent(
                message_id="trigger-123",
                reply=_FeishuReply(
                    message_id="target-456",
                    sender_id="cli-id",
                    sender_id_type="app_id",
                ),
            ),
        ),
        FeishuSelfRevokeProvider,
    )
    assert isinstance(
        registry.resolve(
            _FakeSatoriBot(self_id="10000"),
            _FakeSatoriEvent(
                channel_id="channel-1",
                message_id="trigger-123",
                reply=_SatoriReply(message_id="target-456", author_id="10000"),
            ),
        ),
        SatoriSelfRevokeProvider,
    )
    assert isinstance(
        registry.resolve(
            _FakeBot(adapter_name="QQ", self_id="10000"),
            _FakeChannelEvent(
                adapter_event_type="message_create",
                message_id="trigger-123",
                channel_id="channel-1",
                reply=_FakeMessageGet(message_id="target-456", author_id="10000"),
            ),
        ),
        QQGuildSelfRevokeProvider,
    )


def test_service_revokes_target_and_optional_trigger() -> None:
    provider = _FakeProvider()
    registry = SelfRevokeProviderRegistry((provider,))
    config = SelfRevokeConfig(
        permission="public",
        revoke_trigger_message=True,
        feedback="reaction",
    )

    async def scenario() -> None:
        result = await handle_self_revoke_event(
            _FakeBot(),
            _FakeEvent(),
            config=config,
            registry=registry,
        )

        assert result.status == "target_revoked"
        assert result.target_revoked is True
        assert result.should_stop_propagation is True
        assert provider.calls == [
            "get_reply_target",
            "is_bot_authored",
            "revoke_message:target-1",
            "revoke_trigger_message",
        ]

    asyncio.run(scenario())


def test_service_silently_rejects_unknown_target_author() -> None:
    provider = _FakeProvider(bot_authored=False)
    registry = SelfRevokeProviderRegistry((provider,))
    config = SelfRevokeConfig(permission="public", feedback="silent")

    async def scenario() -> None:
        result = await handle_self_revoke_event(
            _FakeBot(),
            _FakeEvent(),
            config=config,
            registry=registry,
        )

        assert result.status == "not_bot_authored"
        assert result.target_revoked is False
        assert result.should_stop_propagation is True
        assert provider.calls == ["get_reply_target", "is_bot_authored"]

    asyncio.run(scenario())


def test_service_superuser_mode_denies_without_text_feedback(
    monkeypatch: MonkeyPatch,
) -> None:
    provider = _FakeProvider()
    registry = SelfRevokeProviderRegistry((provider,))
    config = SelfRevokeConfig(permission="superuser", feedback="reaction")
    monkeypatch.setattr(
        nonebot,
        "get_driver",
        lambda: SimpleNamespace(config=SimpleNamespace(superusers=set())),
    )

    async def scenario() -> None:
        result = await handle_self_revoke_event(
            _FakeBot(self_id="10000", user_id="20000"),
            _FakeEvent(user_id="20000"),
            config=config,
            registry=registry,
        )

        assert result.status == "permission_denied"
        assert result.target_revoked is False
        assert result.should_stop_propagation is True
        assert provider.calls == ["get_reply_target", "apply_feedback:failure"]

    asyncio.run(scenario())


def test_service_unsupported_provider_does_not_stop_propagation() -> None:
    registry = SelfRevokeProviderRegistry((_UnsupportedProvider(),))

    async def scenario() -> None:
        result = await handle_self_revoke_event(
            _FakeBot(),
            _FakeEvent(),
            config=SelfRevokeConfig(),
            registry=registry,
        )

        assert result.status == "no_provider"
        assert result.should_stop_propagation is False

    asyncio.run(scenario())


@dataclass(frozen=True)
class _ProviderCase:
    name: str
    provider: Any
    bot: Any
    event: Any
    target: RevokeTarget
    api_calls: list[tuple[str, dict[str, object]]]
    revoke_trigger: bool = True


def _bot_authored_revoke_cases() -> tuple[_ProviderCase, ...]:
    onebot_v11_bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    discord_bot = _FakeBot(adapter_name="Discord", self_id="10000")
    discord_bot.self_info = _SimpleUser("10000")
    feishu_bot = _FakeBot(adapter_name="Feishu", self_id="cli-id")
    feishu_bot.bot_config = SimpleNamespace(app_id="app-1")
    qq_bot = _FakeBot(adapter_name="QQ", self_id="10000")
    qq_bot.self_info = _SimpleUser("10000")

    return (
        _ProviderCase(
            name="onebot-v11",
            provider=OneBotV11SelfRevokeProvider(),
            bot=onebot_v11_bot,
            event=_FakeEvent(
                self_id="10000",
                user_id="20000",
                message_id=123,
                reply=_Reply(message_id=456, user_id="10000"),
            ),
            target=RevokeTarget(message_id="456", author_id="10000"),
            api_calls=[("delete_msg", {"message_id": 456})],
            revoke_trigger=False,
        ),
        _ProviderCase(
            name="onebot-v12",
            provider=OneBotV12SelfRevokeProvider(),
            bot=_FakeBot(adapter_name="OneBot V12", self_id="10000"),
            event=_FakeOneBotV12Event(
                self_user_id="10000",
                user_id="20000",
                message_id="trigger-123",
                reply=_OneBotV12Reply(message_id="target-456", user_id="10000"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="10000"),
            api_calls=[
                ("delete_message", {"message_id": "target-456"}),
                ("delete_message", {"message_id": "trigger-123"}),
            ],
        ),
        _ProviderCase(
            name="telegram",
            provider=TelegramSelfRevokeProvider(),
            bot=_FakeBot(adapter_name="Telegram", self_id="10000"),
            event=_FakeTelegramEvent(
                chat_id=-1001,
                message_id=123,
                reply=_FakeTelegramMessage(message_id=456, from_id="10000"),
            ),
            target=RevokeTarget(message_id="456", author_id="10000"),
            api_calls=[
                ("delete_message", {"chat_id": -1001, "message_id": 456}),
                ("delete_message", {"chat_id": -1001, "message_id": 123}),
            ],
        ),
        _ProviderCase(
            name="discord",
            provider=DiscordSelfRevokeProvider(),
            bot=discord_bot,
            event=_FakeChannelEvent(
                adapter_event_type="message_create",
                message_id="trigger-123",
                channel_id="channel-1",
                reply=_FakeMessageGet(message_id="target-456", author_id="10000"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="10000"),
            api_calls=[
                (
                    "delete_message",
                    {"channel_id": "channel-1", "message_id": "target-456"},
                ),
                (
                    "delete_message",
                    {"channel_id": "channel-1", "message_id": "trigger-123"},
                ),
            ],
        ),
        _ProviderCase(
            name="feishu",
            provider=FeishuSelfRevokeProvider(),
            bot=feishu_bot,
            event=_FakeFeishuEvent(
                message_id="trigger-123",
                reply=_FeishuReply(
                    message_id="target-456",
                    sender_id="app-1",
                    sender_id_type="app_id",
                ),
            ),
            target=RevokeTarget(message_id="target-456", author_id="app-1"),
            api_calls=[
                ("im/v1/messages/target-456", {"method": "DELETE"}),
                ("im/v1/messages/trigger-123", {"method": "DELETE"}),
            ],
        ),
        _ProviderCase(
            name="satori",
            provider=SatoriSelfRevokeProvider(),
            bot=_FakeSatoriBot(self_id="bot-1"),
            event=_FakeSatoriEvent(
                channel_id="channel-1",
                message_id="trigger-123",
                reply=_SatoriReply(message_id="target-456", author_id="bot-1"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="bot-1"),
            api_calls=[
                (
                    "message_delete",
                    {"channel_id": "channel-1", "message_id": "target-456"},
                ),
                (
                    "message_delete",
                    {"channel_id": "channel-1", "message_id": "trigger-123"},
                ),
            ],
        ),
        _ProviderCase(
            name="qq-guild",
            provider=QQGuildSelfRevokeProvider(),
            bot=qq_bot,
            event=_FakeChannelEvent(
                adapter_event_type="message_create",
                message_id="trigger-123",
                channel_id="channel-1",
                reply=_FakeMessageGet(message_id="target-456", author_id="10000"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="10000"),
            api_calls=[
                (
                    "delete_message",
                    {"channel_id": "channel-1", "message_id": "target-456"},
                ),
                (
                    "delete_message",
                    {"channel_id": "channel-1", "message_id": "trigger-123"},
                ),
            ],
        ),
    )


def _non_bot_reply_cases() -> tuple[_ProviderCase, ...]:
    feishu_bot = _FakeBot(adapter_name="Feishu", self_id="cli-id")
    feishu_bot.bot_config = SimpleNamespace(app_id="app-1")
    return (
        _ProviderCase(
            name="onebot-v11",
            provider=OneBotV11SelfRevokeProvider(),
            bot=_FakeBot(adapter_name="OneBot V11", self_id="10000"),
            event=_FakeEvent(
                self_id="10000",
                user_id="20000",
                message_id=123,
                reply=_Reply(message_id=456, user_id="20000"),
            ),
            target=RevokeTarget(message_id="456", author_id="20000"),
            api_calls=[],
        ),
        _ProviderCase(
            name="onebot-v12",
            provider=OneBotV12SelfRevokeProvider(),
            bot=_FakeBot(adapter_name="OneBot V12", self_id="10000"),
            event=_FakeOneBotV12Event(
                self_user_id="10000",
                user_id="20000",
                message_id="trigger-123",
                reply=_OneBotV12Reply(message_id="target-456", user_id="20000"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="20000"),
            api_calls=[],
        ),
        _ProviderCase(
            name="telegram",
            provider=TelegramSelfRevokeProvider(),
            bot=_FakeBot(adapter_name="Telegram", self_id="10000"),
            event=_FakeTelegramEvent(
                chat_id=-1001,
                message_id=123,
                reply=_FakeTelegramMessage(message_id=456, from_id="20000"),
            ),
            target=RevokeTarget(message_id="456", author_id="20000"),
            api_calls=[],
        ),
        _ProviderCase(
            name="discord",
            provider=DiscordSelfRevokeProvider(),
            bot=_FakeBot(adapter_name="Discord", self_id="10000"),
            event=_FakeChannelEvent(
                adapter_event_type="message_create",
                message_id="trigger-123",
                channel_id="channel-1",
                reply=_FakeMessageGet(message_id="target-456", author_id="20000"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="20000"),
            api_calls=[],
        ),
        _ProviderCase(
            name="feishu",
            provider=FeishuSelfRevokeProvider(),
            bot=feishu_bot,
            event=_FakeFeishuEvent(
                message_id="trigger-123",
                reply=_FeishuReply(
                    message_id="target-456",
                    sender_id="app-1",
                    sender_id_type="open_id",
                ),
            ),
            target=RevokeTarget(message_id="target-456", author_id="app-1"),
            api_calls=[],
        ),
        _ProviderCase(
            name="satori",
            provider=SatoriSelfRevokeProvider(),
            bot=_FakeSatoriBot(self_id="bot-1"),
            event=_FakeSatoriEvent(
                channel_id="channel-1",
                message_id="trigger-123",
                reply=_SatoriReply(message_id="target-456", author_id="user-2"),
            ),
            target=RevokeTarget(message_id="target-456", author_id="user-2"),
            api_calls=[],
        ),
    )


class _FakeAdapter:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _FakeBot:
    def __init__(
        self,
        *,
        adapter_name: str = "OneBot V11",
        self_id: str = "10000",
        user_id: str = "20000",
        fail_apis: set[str] | None = None,
    ) -> None:
        self.adapter = _FakeAdapter(adapter_name)
        self.self_id = self_id
        self.user_id = user_id
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._fail_apis = fail_apis or set()

    @property
    def type(self) -> str:
        return self.adapter.get_name()

    async def call_api(self, api: str, **data: object) -> object:
        self.calls.append((api, data))
        if api in self._fail_apis:
            msg = f"{api} failed"
            raise RuntimeError(msg)
        return {"status": "ok"}


class _FakeSatoriBot(_FakeBot):
    def __init__(
        self,
        *,
        self_id: str,
        fetched_author_id: str | None = None,
    ) -> None:
        super().__init__(adapter_name="Satori", self_id=f"satori:{self_id}")
        self._satori_self_id = self_id
        self._satori_fetched_author_id = fetched_author_id

    def get_self_id(self) -> str:
        return self._satori_self_id

    async def call_api(self, api: str, **data: object) -> object:
        if api == "message_get":
            self.calls.append((api, data))
            if self._satori_fetched_author_id is not None:
                return SimpleNamespace(
                    user=SimpleNamespace(id=self._satori_fetched_author_id),
                )
            return SimpleNamespace(user=None)
        return await super().call_api(api, **data)


class _Sender:
    def __init__(self, user_id: str | None) -> None:
        self.user_id = user_id


class _Reply:
    def __init__(self, *, message_id: int | str, user_id: str | None) -> None:
        self.message_id = message_id
        self.sender = _Sender(user_id)


class _OneBotV12Reply:
    def __init__(self, *, message_id: str, user_id: str | None) -> None:
        self.message_id = message_id
        self.user_id = user_id


class _SimpleUser:
    def __init__(self, user_id: str | int) -> None:
        self.id = user_id


class _BotSelf:
    def __init__(self, user_id: str | None) -> None:
        self.user_id = user_id


class _FakeEvent:
    def __init__(
        self,
        *,
        self_id: str = "10000",
        user_id: str = "20000",
        message_id: int | str = 123,
        reply: object | None = None,
    ) -> None:
        self.self_id = self_id
        self.user_id = user_id
        self.message_id = message_id
        self.reply = reply

    def get_user_id(self) -> str:
        return self.user_id


class _FakeOneBotV12Event:
    def __init__(
        self,
        *,
        self_user_id: str = "10000",
        user_id: str = "20000",
        message_id: str = "trigger-123",
        reply: object | None = None,
    ) -> None:
        self.self = _BotSelf(self_user_id)
        self.user_id = user_id
        self.message_id = message_id
        self.reply = reply

    def get_user_id(self) -> str:
        return self.user_id


class _FakeTelegramMessage:
    def __init__(self, *, message_id: int | str, from_id: int | str) -> None:
        self.message_id = message_id
        self.from_ = _SimpleUser(from_id)


class _FakeTelegramEvent:
    def __init__(
        self,
        *,
        chat_id: int | str,
        message_id: int | str,
        reply: object | None,
    ) -> None:
        self.chat = SimpleNamespace(id=chat_id)
        self.message_id = message_id
        self.reply_to_message = reply

    def get_user_id(self) -> str:
        return "20000"


class _FeishuReplySender:
    def __init__(self, *, sender_id: str, sender_id_type: str) -> None:
        self.id = sender_id
        self.id_type = sender_id_type


class _FeishuReply:
    def __init__(
        self,
        *,
        message_id: str,
        sender_id: str,
        sender_id_type: str,
    ) -> None:
        self.message_id = message_id
        self.sender = _FeishuReplySender(
            sender_id=sender_id,
            sender_id_type=sender_id_type,
        )


class _FakeFeishuEvent:
    def __init__(self, *, message_id: str, reply: object | None) -> None:
        self.message_id = message_id
        self.reply = reply

    def get_user_id(self) -> str:
        return "ou-user"


class _FakeMessageGet:
    def __init__(self, *, message_id: str, author_id: str) -> None:
        self.id = message_id
        self.author = _SimpleUser(author_id)


class _SatoriAuthor:
    def __init__(self, author_id: str) -> None:
        self.data = {"id": author_id}


class _SatoriChildren:
    def __init__(self, author_id: str | None) -> None:
        self._author_id = author_id

    def get(self, item_type: str) -> list[object]:
        if item_type == "author" and self._author_id is not None:
            return [_SatoriAuthor(self._author_id)]
        return []


class _SatoriReply:
    def __init__(self, *, message_id: str, author_id: str | None) -> None:
        self.data = {"id": message_id}
        self.children = _SatoriChildren(author_id)


class _FakeSatoriEvent:
    def __init__(
        self,
        *,
        channel_id: str,
        message_id: str,
        reply: object | None,
    ) -> None:
        self.channel = SimpleNamespace(id=channel_id)
        self.message = SimpleNamespace(id=message_id)
        self.msg_id = message_id
        self.reply = reply

    def get_user_id(self) -> str:
        return "user-1"


class _FakeChannelEvent:
    def __init__(
        self,
        *,
        adapter_event_type: str,
        message_id: str,
        channel_id: str,
        reply: object | None,
    ) -> None:
        self.__type__ = adapter_event_type
        self.id = message_id
        self.message_id = message_id
        self.channel_id = channel_id
        self.reply = reply

    def get_user_id(self) -> str:
        return "20000"


class _FakeProvider:
    def __init__(
        self,
        *,
        target: RevokeTarget | None = RevokeTarget(
            message_id="target-1",
            author_id="10000",
        ),
        bot_authored: bool = True,
        revoke_result: RevokeActionResult | None = None,
    ) -> None:
        self.target = target
        self.bot_authored = bot_authored
        self.revoke_result = revoke_result or RevokeActionResult.succeeded()
        self.calls: list[str] = []

    def supports(self, bot: object, event: object) -> bool:  # noqa: ARG002
        return True

    async def get_reply_target(self, bot: object, event: object) -> RevokeTarget | None:  # noqa: ARG002
        self.calls.append("get_reply_target")
        return self.target

    async def is_bot_authored(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
        target: RevokeTarget,  # noqa: ARG002
    ) -> bool:
        self.calls.append("is_bot_authored")
        return self.bot_authored

    async def revoke_message(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
        target: RevokeTarget,
    ) -> RevokeActionResult:
        self.calls.append(f"revoke_message:{target.message_id}")
        return self.revoke_result

    async def revoke_trigger_message(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
    ) -> RevokeActionResult:
        self.calls.append("revoke_trigger_message")
        return RevokeActionResult.succeeded()

    async def apply_feedback(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
        *,
        kind: str,
    ) -> RevokeActionResult:
        self.calls.append(f"apply_feedback:{kind}")
        return RevokeActionResult.succeeded()


class _UnsupportedProvider(_FakeProvider):
    def supports(self, bot: object, event: object) -> bool:  # noqa: ARG002
        return False
