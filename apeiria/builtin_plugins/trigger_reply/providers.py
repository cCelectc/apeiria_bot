from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from nonebot.log import logger

from apeiria.bot.platform import (
    ActionResult,
    adapter_name,
    call_platform_api,
    event_group_id,
    event_message_id,
    event_user_id,
    id_value,
    string_attr,
)

from .models import TriggerInput

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_PLATFORM_ALIASES = {
    _ONEBOT_V11_ADAPTER_NAME: "qq",
}


@dataclass(frozen=True, slots=True)
class TriggerReplySendResult(ActionResult):
    """Result for bounded trigger-reply delivery."""


class MessageInputProvider(Protocol):
    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    def normalize(self, bot: "Bot", event: "Event") -> TriggerInput | None: ...


class PokeInputProvider(Protocol):
    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    def normalize(self, bot: "Bot", event: "Event") -> TriggerInput | None: ...

    async def send_reply(
        self,
        bot: "Bot",
        trigger: TriggerInput,
        *,
        message: str,
    ) -> TriggerReplySendResult: ...


class MessageInputProviderRegistry:
    def __init__(self, providers: tuple[MessageInputProvider, ...]) -> None:
        self._providers = providers

    def normalize(self, bot: "Bot", event: "Event") -> TriggerInput | None:
        for provider in self._providers:
            if not _provider_supports(provider, bot, event, "message input provider"):
                continue
            trigger = provider.normalize(bot, event)
            if trigger is not None:
                return trigger
        return None


class PokeInputProviderRegistry:
    def __init__(self, providers: tuple[PokeInputProvider, ...]) -> None:
        self._providers = providers

    def resolve(self, bot: "Bot", event: "Event") -> PokeInputProvider | None:
        for provider in self._providers:
            if _provider_supports(provider, bot, event, "poke input provider"):
                return provider
        return None


class NoneBotMessageInputProvider:
    def supports(self, bot: "Bot", event: "Event") -> bool:  # noqa: ARG002
        try:
            return event.get_type() == "message"
        except Exception:  # noqa: BLE001
            return False

    def normalize(self, bot: "Bot", event: "Event") -> TriggerInput | None:
        message_text = _message_text(event)
        return TriggerInput(
            source="message",
            platform=_platform_from_bot(bot),
            bot_id=_bot_id(bot),
            user_id=event_user_id(event),
            group_id=_event_group_scope(event),
            message_id=event_message_id(event),
            message_text=message_text,
            plaintext=_plaintext(event) or message_text,
            is_to_me=_is_to_me(event),
        )


class OneBotV11PokeInputProvider:
    """OneBot v11 provider for QQ poke recognition and delivery."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        return (
            adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME
            and string_attr(event, "notice_type") == "notify"
            and string_attr(event, "sub_type") == "poke"
        )

    def normalize(self, bot: "Bot", event: "Event") -> TriggerInput | None:
        user_id = event_user_id(event)
        target_id = string_attr(event, "target_id")
        if user_id is None or target_id is None:
            return None
        bot_id = _bot_id(bot)
        return TriggerInput(
            source="poke",
            platform=_platform_from_bot(bot),
            bot_id=bot_id,
            user_id=user_id,
            group_id=event_group_id(event),
            target_id=target_id,
            is_to_me=bot_id is not None and target_id == bot_id,
        )

    async def send_reply(
        self,
        bot: "Bot",
        trigger: TriggerInput,
        *,
        message: str,
    ) -> TriggerReplySendResult:
        data: dict[str, object] = {"message": message}
        if trigger.group_id is not None:
            data["group_id"] = id_value(trigger.group_id)
            data["message_type"] = "group"
        elif trigger.user_id is not None:
            data["user_id"] = id_value(trigger.user_id)
            data["message_type"] = "private"
        else:
            return TriggerReplySendResult.unsupported("reply_target_unavailable")
        return await call_platform_api(
            bot,
            "send_msg",
            data=data,
            result_type=TriggerReplySendResult,
            log_label="Trigger reply OneBot",
        )


def _provider_supports(
    provider: object,
    bot: "Bot",
    event: "Event",
    label: str,
) -> bool:
    supports = getattr(provider, "supports", None)
    if not callable(supports):
        return False
    try:
        return bool(supports(bot, event))
    except Exception as exc:  # noqa: BLE001
        logger.debug("{} support check failed: {}", label, exc)
        return False


def _platform_from_bot(bot: object) -> str | None:
    platform = adapter_name(bot)
    return _PLATFORM_ALIASES.get(platform, platform) or None


def _bot_id(bot: object) -> str | None:
    return string_attr(bot, "self_id")


def _event_group_scope(event: object) -> str | None:
    group_id = event_group_id(event)
    if group_id is not None:
        return group_id
    guild_id = string_attr(event, "guild_id")
    channel_id = string_attr(event, "channel_id")
    if guild_id is not None and channel_id is not None:
        return f"{guild_id}/{channel_id}"
    return guild_id or channel_id


def _message_text(event: object) -> str:
    get_message = getattr(event, "get_message", None)
    if not callable(get_message):
        message = getattr(event, "message", "")
        return str(message)
    try:
        return str(cast("object", get_message()))
    except Exception:  # noqa: BLE001
        message = getattr(event, "message", "")
        return str(message)


def _plaintext(event: object) -> str:
    get_plaintext = getattr(event, "get_plaintext", None)
    if not callable(get_plaintext):
        return ""
    try:
        return str(cast("object", get_plaintext()))
    except Exception:  # noqa: BLE001
        return ""


def _is_to_me(event: object) -> bool:
    is_tome = getattr(event, "is_tome", None)
    if not callable(is_tome):
        return False
    try:
        return bool(cast("object", is_tome()))
    except Exception:  # noqa: BLE001
        return False


message_input_provider_registry = MessageInputProviderRegistry(
    providers=(NoneBotMessageInputProvider(),)
)
poke_input_provider_registry = PokeInputProviderRegistry(
    providers=(OneBotV11PokeInputProvider(),)
)


__all__ = [
    "MessageInputProvider",
    "MessageInputProviderRegistry",
    "NoneBotMessageInputProvider",
    "OneBotV11PokeInputProvider",
    "PokeInputProvider",
    "PokeInputProviderRegistry",
    "TriggerReplySendResult",
    "message_input_provider_registry",
    "poke_input_provider_registry",
]
