from __future__ import annotations

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


def test_repeater_config_and_service_decide_on_repeated_group_text() -> None:
    config = RepeaterConfig.model_validate(normalize_repeater_config({}))
    command_key = build_content_key(_text_message("/help"))
    text_key = build_content_key(_text_message("哈"))
    probability = repeat_probability(
        2,
        repeat_threshold=config.repeat_threshold,
        base_probability=config.base_probability,
        max_probability=config.max_probability,
        saturation_extra=config.saturation_extra,
    )

    assert command_key.status == "unsupported"
    assert command_key.reason == "ignored_prefix"
    assert text_key.status == "supported"
    assert text_key.key == (("text", "哈"),)
    assert probability == config.base_probability

    service = RepeaterService(random_draw=lambda: 0.0)
    active_config = _active_config()
    message = _text_message("哈")
    first = service.evaluate(_event("u1", message), config=active_config)
    second = service.evaluate(_event("u2", message), config=active_config)

    assert first.reason == "below_threshold"
    assert second.should_send is True
    assert second.message == message
    assert second.group_scope == "qq:100"


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
