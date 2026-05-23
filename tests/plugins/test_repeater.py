from __future__ import annotations

import asyncio
import importlib
from typing import TYPE_CHECKING

from apeiria.builtin_plugins.repeater.config import (
    RepeaterConfig,
    normalize_repeater_config,
)
from apeiria.builtin_plugins.repeater.service import (
    RepeaterEvent,
    RepeaterService,
    build_content_key,
    repeat_probability,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_repeater_config_and_service_smoke() -> None:
    config = RepeaterConfig.model_validate(normalize_repeater_config({}))
    build_content_key(_text_message("/help"))
    build_content_key(_text_message("哈"))
    repeat_probability(
        2,
        repeat_threshold=config.repeat_threshold,
        base_probability=config.base_probability,
        max_probability=config.max_probability,
        saturation_extra=config.saturation_extra,
    )

    service = RepeaterService(random_draw=lambda: 0.0)
    active_config = _active_config()
    message = _text_message("哈")
    service.evaluate(_event("u1", message), config=active_config)
    service.evaluate(_event("u2", message), config=active_config)


def test_repeater_plugin_handler_smoke(monkeypatch: MonkeyPatch) -> None:
    module = importlib.import_module("apeiria.builtin_plugins.repeater")
    service = RepeaterService(random_draw=lambda: 0.0)
    monkeypatch.setattr(module, "get_repeater_config", _active_config)
    monkeypatch.setattr(module, "default_repeater_service", service)

    async def scenario() -> None:
        matcher = _FakeMatcher()
        message = _text_message("哈")
        await module.handle_repeater(
            _FakeBot(),
            _FakeEvent(user_id="u1", group_id="100", message=message),
            matcher,
        )
        await module.handle_repeater(
            _FakeBot(),
            _FakeEvent(user_id="u2", group_id="100", message=message),
            matcher,
        )

    asyncio.run(scenario())


def _active_config() -> RepeaterConfig:
    return RepeaterConfig(
        group_mode="allowlist",
        allow_groups=frozenset({"qq:100"}),
    )


def _event(user_id: str, message: object) -> RepeaterEvent:
    return RepeaterEvent(
        platform="qq",
        group_id="100",
        user_id=user_id,
        bot_id="bot",
        message=message,
    )


def _text_message(text: str) -> list[dict[str, object]]:
    return [{"type": "text", "data": {"text": text}}]


class _FakeBot:
    type = "qq"
    self_id = "bot"


class _FakeEvent:
    def __init__(
        self,
        *,
        user_id: str,
        group_id: str | None,
        message: object,
    ) -> None:
        self.user_id = user_id
        self.group_id = group_id
        self.message = message

    def get_user_id(self) -> str:
        return self.user_id

    def get_message(self) -> object:
        return self.message

    def get_session_id(self) -> str:
        if self.group_id is None:
            return f"private_{self.user_id}"
        return f"group_{self.group_id}_{self.user_id}"


class _FakeMatcher:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, message: object) -> None:
        self.sent.append(message)
