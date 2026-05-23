from __future__ import annotations

import asyncio
import importlib
from typing import Any, cast

from apeiria.builtin_plugins.contact_owner.config import (
    DEFAULT_CONTACT_PREFIX,
    ContactOwnerConfig,
    normalize_contact_owner_config,
)
from apeiria.builtin_plugins.contact_owner.providers import (
    ContactOwnerDeliveryResult,
    ContactOwnerProviderRegistry,
    OneBotV11ContactOwnerProvider,
    OwnerTarget,
    parse_owner_target,
)
from apeiria.builtin_plugins.contact_owner.service import (
    extract_contact_message_body,
    handle_contact_owner_event,
)


def test_contact_owner_config_normalizes_bounded_values() -> None:
    minimum_length = 5
    config = normalize_contact_owner_config(
        {
            "contact_prefix": "  找主人  ",
            "owner_target": "  qq:123456  ",
            "minimum_message_length": str(minimum_length),
            "empty_message_reply": "",
        }
    )
    assert config["contact_prefix"] == "找主人"
    assert config["owner_target"] == "qq:123456"
    assert config["minimum_message_length"] == minimum_length
    assert config["empty_message_reply"]
    assert (
        normalize_contact_owner_config(
            {
                "contact_prefix": "",
                "minimum_message_length": -1,
            }
        )["contact_prefix"]
        == DEFAULT_CONTACT_PREFIX
    )


def test_owner_target_parsing_is_scoped_and_bounded() -> None:
    assert parse_owner_target(" qq:123456 ") == OwnerTarget(
        scope="qq",
        target_id="123456",
    )
    assert parse_owner_target("telegram:abc") == OwnerTarget(
        scope="telegram",
        target_id="abc",
    )
    assert parse_owner_target("123456") is None
    assert parse_owner_target("qq:0") is None
    assert parse_owner_target("qq:not-number") is None


def test_contact_message_body_extraction_uses_literal_prefix() -> None:
    assert (
        extract_contact_message_body(
            "  联系主人 你好",
            prefix="联系主人",
        )
        == "你好"
    )
    assert extract_contact_message_body("请联系主人", prefix="联系主人") is None


def test_contact_owner_service_validates_and_reports_failures() -> None:
    async def scenario() -> None:
        bot = _FakeBot(adapter_name="Console", self_id="10000")
        event = _FakeEvent(user_id="20000", group_id="30000", message_id="msg-1")

        ignored = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="普通消息",
            config=ContactOwnerConfig(owner_target="qq:123456"),
        )
        assert ignored.status == "ignored"
        assert ignored.should_stop_propagation is False

        empty = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人   ",
            config=ContactOwnerConfig(owner_target="qq:123456"),
        )
        assert empty.status == "empty_message"
        assert empty.should_stop_propagation is True

        too_short = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好",
            config=ContactOwnerConfig(
                owner_target="qq:123456",
                minimum_message_length=2,
            ),
        )
        assert too_short.status == "too_short"

        unconfigured = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好啊",
            config=ContactOwnerConfig(owner_target=""),
        )
        assert unconfigured.status == "owner_unconfigured"

        invalid = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好啊",
            config=ContactOwnerConfig(owner_target="qq:not-number"),
        )
        assert invalid.status == "invalid_owner_target"

        unsupported = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好啊",
            config=ContactOwnerConfig(owner_target="qq:123456"),
            registry=ContactOwnerProviderRegistry(()),
        )
        assert unsupported.status == "unsupported_platform"

        failed = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好啊",
            config=ContactOwnerConfig(owner_target="qq:123456"),
            registry=ContactOwnerProviderRegistry(
                (
                    _FakeProvider(
                        result=ContactOwnerDeliveryResult.failed(),
                    ),
                )
            ),
        )
        assert failed.status == "delivery_failed"

    asyncio.run(scenario())


def test_contact_owner_service_delivers_bounded_owner_message() -> None:
    provider = _FakeProvider()
    registry = ContactOwnerProviderRegistry((provider,))
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000", group_id="30000", message_id="msg-1")

    async def scenario() -> None:
        result = await handle_contact_owner_event(
            cast("Any", bot),
            cast("Any", event),
            message_text="联系主人 你好，我遇到问题了",
            config=ContactOwnerConfig(owner_target="qq:123456"),
            registry=registry,
        )

        assert result.status == "delivered"
        assert result.reply
        assert result.should_stop_propagation is True
        assert len(provider.calls) == 1
        target, message = provider.calls[0]
        assert target == OwnerTarget(scope="qq", target_id="123456")
        assert "你好，我遇到问题了" in message
        assert "20000" in message
        assert "30000" in message
        assert "msg-1" in message

    asyncio.run(scenario())


def test_onebot_contact_owner_provider_sends_private_message() -> None:
    provider = OneBotV11ContactOwnerProvider()
    bot = _FakeBot(adapter_name="OneBot V11", self_id="10000")
    event = _FakeEvent(user_id="20000")
    target = OwnerTarget(scope="qq", target_id="123456")

    async def scenario() -> None:
        assert provider.supports(cast("Any", bot), cast("Any", event), target)
        result = await provider.deliver_owner_message(
            cast("Any", bot),
            cast("Any", event),
            target,
            message="hello",
        )

        assert result.success
        assert bot.calls == [
            ("send_private_msg", {"user_id": 123456, "message": "hello"})
        ]

    asyncio.run(scenario())

    failing_bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        fail_apis={"send_private_msg"},
    )

    async def failing_scenario() -> None:
        result = await provider.deliver_owner_message(
            cast("Any", failing_bot),
            cast("Any", event),
            target,
            message="hello",
        )

        assert result.status == "failed"

    asyncio.run(failing_scenario())


def test_contact_owner_plugin_metadata_declares_core_config() -> None:
    module = importlib.import_module("apeiria.builtin_plugins.contact_owner")

    assert module.__plugin_meta__.name == "联系主人"
    assert module.__plugin_meta__.type == "application"
    fields = {
        field["key"]: field
        for field in module.__plugin_meta__.extra["config"]["fields"]
    }
    assert fields["contact_prefix"]["default"] == DEFAULT_CONTACT_PREFIX
    assert fields["owner_target"]["default"] == ""
    assert fields["minimum_message_length"]["default"] == 0


class _FakeProvider:
    def __init__(
        self,
        *,
        result: ContactOwnerDeliveryResult | None = None,
    ) -> None:
        self.result = result or ContactOwnerDeliveryResult.succeeded()
        self.calls: list[tuple[OwnerTarget, str]] = []

    def supports(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
        target: OwnerTarget,  # noqa: ARG002
    ) -> bool:
        return True

    async def deliver_owner_message(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactOwnerDeliveryResult:
        self.calls.append((target, message))
        return self.result


class _FakeBot:
    def __init__(
        self,
        *,
        adapter_name: str,
        self_id: str,
        fail_apis: set[str] | None = None,
    ) -> None:
        self.type = adapter_name
        self.self_id = self_id
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.fail_apis = fail_apis or set()

    async def call_api(self, api: str, **data: object) -> object:
        self.calls.append((api, data))
        if api in self.fail_apis:
            msg = f"{api} failed"
            raise RuntimeError(msg)
        return {}


class _FakeEvent:
    def __init__(
        self,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        message_id: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.group_id = group_id
        self.message_id = message_id

    def get_user_id(self) -> str:
        return str(self.user_id or "")

    def get_message_id(self) -> str:
        return str(self.message_id or "")

    def get_plaintext(self) -> str:
        return ""
