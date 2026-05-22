from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import apeiria.builtin_plugins.self_revoke.service as self_revoke_service
from apeiria.builtin_plugins.self_revoke.config import (
    SelfRevokeConfig,
    normalize_self_revoke_config,
)
from apeiria.builtin_plugins.self_revoke.providers import (
    OneBotSelfRevokeProvider,
    RevokeActionResult,
    RevokeTarget,
    SelfRevokeProviderRegistry,
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


def test_prefixed_trigger_matching_uses_configured_prefixes(
    monkeypatch: MonkeyPatch,
) -> None:
    module = importlib.import_module("apeiria.builtin_plugins.self_revoke")
    monkeypatch.setattr(
        module,
        "get_driver",
        lambda: SimpleNamespace(config=SimpleNamespace(command_start={"/", "!"})),
    )

    async def scenario() -> None:
        assert await module._is_prefixed_self_revoke_message(_TextEvent("/撤回"))
        assert await module._is_prefixed_self_revoke_message(_TextEvent("!ReVoKe"))
        assert not await module._is_prefixed_self_revoke_message(_TextEvent("撤回"))
        assert not await module._is_prefixed_self_revoke_message(_TextEvent("/请撤回"))

    asyncio.run(scenario())


def test_handler_stops_only_for_handled_revoke_intents(
    monkeypatch: MonkeyPatch,
) -> None:
    module = importlib.import_module("apeiria.builtin_plugins.self_revoke")
    handled = self_revoke_service.SelfRevokeHandleResult(
        status="target_revoked",
        should_stop_propagation=True,
    )
    ignored = self_revoke_service.SelfRevokeHandleResult(status="no_reply_target")

    async def fake_handle(
        _bot: object,
        _event: object,
        *,
        config: object | None = None,
    ) -> self_revoke_service.SelfRevokeHandleResult:
        del config
        return handled

    monkeypatch.setattr(module, "handle_self_revoke_event", fake_handle)

    async def scenario() -> None:
        matcher = _FakeMatcher()
        await module.handle_revoke(_FakeBot(), _FakeEvent(), matcher)
        assert matcher.stopped is True

        async def fake_ignored(
            _bot: object,
            _event: object,
            *,
            config: object | None = None,
        ) -> self_revoke_service.SelfRevokeHandleResult:
            del config
            return ignored

        monkeypatch.setattr(module, "handle_self_revoke_event", fake_ignored)
        matcher = _FakeMatcher()
        await module.handle_revoke(_FakeBot(), _FakeEvent(), matcher)
        assert matcher.stopped is False

    asyncio.run(scenario())


def test_prefixless_matcher_accepts_english_case_variants() -> None:
    module = importlib.import_module("apeiria.builtin_plugins.self_revoke")

    rule_repr = repr(module._prefixless_revoke.rule)
    assert module._prefixless_revoke.rule.checkers
    assert "Fullmatch(" in rule_repr
    assert "ignorecase=True" in rule_repr


def test_self_revoke_plugin_metadata_declares_config() -> None:
    module = importlib.import_module("apeiria.builtin_plugins.self_revoke")

    assert module.__plugin_meta__.name == "自助撤回"
    extra_config = module.__plugin_meta__.extra["config"]
    fields = {field["key"]: field for field in extra_config["fields"]}
    assert fields["permission"]["default"] == "public"
    assert fields["permission"]["choices"] == ["public", "superuser"]
    assert fields["revoke_trigger_message"]["default"] is False
    assert fields["feedback"]["choices"] == ["silent", "reaction"]


def test_onebot_provider_confirms_and_revokes_bot_authored_reply() -> None:
    provider = OneBotSelfRevokeProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(
        self_id="10000",
        user_id="20000",
        message_id=123,
        reply=_Reply(message_id=456, user_id="10000"),
    )

    async def scenario() -> None:
        target = await provider.get_reply_target(bot, event)
        assert target == RevokeTarget(message_id="456", author_id="10000")
        assert target is not None
        assert await provider.is_bot_authored(bot, event, target)

        result = await provider.revoke_message(bot, event, target)

        assert result.success
        assert bot.calls == [("delete_msg", {"message_id": 456})]

    asyncio.run(scenario())


def test_onebot_provider_rejects_non_bot_reply() -> None:
    provider = OneBotSelfRevokeProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(
        self_id="10000",
        user_id="20000",
        message_id=123,
        reply=_Reply(message_id=456, user_id="20000"),
    )

    async def scenario() -> None:
        target = await provider.get_reply_target(bot, event)
        assert target is not None
        assert not await provider.is_bot_authored(bot, event, target)

    asyncio.run(scenario())


def test_onebot_provider_reaction_is_best_effort() -> None:
    provider = OneBotSelfRevokeProvider()
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
        self_revoke_service.nonebot,
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


class _Sender:
    def __init__(self, user_id: str | None) -> None:
        self.user_id = user_id


class _Reply:
    def __init__(self, *, message_id: int | str, user_id: str | None) -> None:
        self.message_id = message_id
        self.sender = _Sender(user_id)


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


class _TextEvent:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_plaintext(self) -> str:
        return self.text


class _FakeMatcher:
    def __init__(self) -> None:
        self.stopped = False

    def stop_propagation(self) -> None:
        self.stopped = True


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
