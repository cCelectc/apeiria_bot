"""Adapter-aware QQ action providers for AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from apeiria.bot.platform import (
    ActionResult,
    ActionStatus,
    ProviderRegistry,
    adapter_name,
    call_platform_api,
    event_group_id,
    event_message_id,
    event_user_id,
    id_value,
)

QQReaction = Literal["like"]
QQActionStatus = ActionStatus

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_ONEBOT_LIKE_EMOJI_ID = "124"


@dataclass(frozen=True, slots=True)
class QQActionResult(ActionResult):
    """Provider-neutral result for one bounded QQ action."""


@dataclass(frozen=True, slots=True)
class QQPokeRequest:
    """Provider-neutral request to poke the current actor."""

    user_id: str
    group_id: str | None = None


@dataclass(frozen=True, slots=True)
class QQMessageReactionRequest:
    """Provider-neutral request to react to the current/source message."""

    message_id: str
    reaction: QQReaction


class QQToolProvider(Protocol):
    """Adapter capability boundary consumed by QQ AI tools."""

    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    async def poke_current_actor(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQActionResult: ...

    async def react_to_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        reaction: QQReaction,
    ) -> QQActionResult: ...


class QQToolProviderRegistry(ProviderRegistry[QQToolProvider]):
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(self, providers: tuple[QQToolProvider, ...]) -> None:
        super().__init__(providers, label="QQ tools provider")


class OneBotV11QQToolProvider:
    """OneBot v11 provider for bounded QQ current-scene actions."""

    def supports(self, bot: "Bot", event: "Event") -> bool:  # noqa: ARG002
        return adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME

    async def poke_current_actor(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQActionResult:
        request = _poke_request_from_event(event)
        if request is None:
            return QQActionResult.unsupported("poke_target_unavailable")

        payload: dict[str, object] = {"user_id": id_value(request.user_id)}
        if request.group_id is not None:
            payload["group_id"] = id_value(request.group_id)
            payload["target_id"] = id_value(request.user_id)

        return await _call_onebot_api(bot, "send_poke", **payload)

    async def react_to_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        reaction: QQReaction,
    ) -> QQActionResult:
        request = _reaction_request_from_event(event, reaction=reaction)
        if request is None:
            return QQActionResult.unsupported("message_target_unavailable")

        return await _call_onebot_api(
            bot,
            "set_msg_emoji_like",
            message_id=_message_id_value(request.message_id),
            emoji_id=_emoji_id_for_reaction(request.reaction),
        )


def _poke_request_from_event(event: object) -> QQPokeRequest | None:
    user_id = event_user_id(event)
    if user_id is None:
        return None
    return QQPokeRequest(
        user_id=user_id,
        group_id=event_group_id(event),
    )


def _reaction_request_from_event(
    event: object,
    *,
    reaction: QQReaction,
) -> QQMessageReactionRequest | None:
    message_id = event_message_id(event)
    if message_id is None:
        return None
    return QQMessageReactionRequest(message_id=message_id, reaction=reaction)


def _message_id_value(message_id: str) -> int | str:
    return id_value(message_id)


def _emoji_id_for_reaction(reaction: QQReaction) -> str:
    emoji_ids: dict[QQReaction, str] = {"like": _ONEBOT_LIKE_EMOJI_ID}
    return emoji_ids[reaction]


async def _call_onebot_api(
    bot: "Bot",
    api: str,
    **data: object,
) -> QQActionResult:
    return await call_platform_api(
        bot,
        api,
        data=data,
        result_type=QQActionResult,
        log_label="QQ tools OneBot",
    )


qq_tool_provider_registry = QQToolProviderRegistry(
    providers=(OneBotV11QQToolProvider(),)
)


__all__ = [
    "OneBotV11QQToolProvider",
    "QQActionResult",
    "QQMessageReactionRequest",
    "QQPokeRequest",
    "QQReaction",
    "QQToolProvider",
    "QQToolProviderRegistry",
    "qq_tool_provider_registry",
]
