"""Adapter-aware QQ action providers for AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from nonebot.log import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nonebot.adapters import Bot, Event

QQReaction = Literal["like"]
QQActionStatus = Literal["success", "failed", "unsupported"]

_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_ONEBOT_LIKE_EMOJI_ID = "124"


@dataclass(frozen=True, slots=True)
class QQActionResult:
    """Provider-neutral result for one bounded QQ action."""

    status: QQActionStatus
    reason: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    @classmethod
    def succeeded(cls) -> "QQActionResult":
        return cls(status="success")

    @classmethod
    def failed(cls, reason: str = "platform_operation_failed") -> "QQActionResult":
        return cls(status="failed", reason=reason)

    @classmethod
    def unsupported(cls, reason: str = "unsupported") -> "QQActionResult":
        return cls(status="unsupported", reason=reason)


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


class QQToolProviderRegistry:
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(self, providers: tuple[QQToolProvider, ...]) -> None:
        self._providers = providers

    def resolve(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQToolProvider | None:
        for provider in self._providers:
            if self._provider_supports(provider, bot, event):
                return provider
        return None

    def _provider_supports(
        self,
        provider: QQToolProvider,
        bot: "Bot",
        event: "Event",
    ) -> bool:
        try:
            return provider.supports(bot, event)
        except Exception as exc:  # noqa: BLE001
            logger.debug("QQ tools provider support check failed: {}", exc)
            return False


class OneBotV11QQToolProvider:
    """OneBot v11 provider for bounded QQ current-scene actions."""

    def supports(self, bot: "Bot", event: "Event") -> bool:  # noqa: ARG002
        return _normalized_adapter_name(bot) == _ONEBOT_V11_ADAPTER_NAME

    async def poke_current_actor(
        self,
        bot: "Bot",
        event: "Event",
    ) -> QQActionResult:
        request = _poke_request_from_event(event)
        if request is None:
            return QQActionResult.unsupported("poke_target_unavailable")

        payload: dict[str, object] = {"user_id": _id_value(request.user_id)}
        if request.group_id is not None:
            payload["group_id"] = _id_value(request.group_id)
            payload["target_id"] = _id_value(request.user_id)

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
    user_id = _event_user_id(event)
    if user_id is None:
        return None
    return QQPokeRequest(
        user_id=user_id,
        group_id=_event_group_id(event),
    )


def _reaction_request_from_event(
    event: object,
    *,
    reaction: QQReaction,
) -> QQMessageReactionRequest | None:
    message_id = _event_message_id(event)
    if message_id is None:
        return None
    return QQMessageReactionRequest(message_id=message_id, reaction=reaction)


def _normalized_adapter_name(bot: object) -> str:
    adapter_name = str(getattr(bot, "type", "") or "").lower()
    return adapter_name.replace(" ", "")


def _string_attr(value: object, name: str) -> str | None:
    try:
        item = getattr(value, name, None)
    except Exception:  # noqa: BLE001
        return None
    if item is None:
        return None
    text = str(item).strip()
    return text or None


def _event_user_id(event: object) -> str | None:
    getter = getattr(event, "get_user_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and str(value).strip():
            return str(value).strip()
    return _string_attr(event, "user_id")


def _event_group_id(event: object) -> str | None:
    return _string_attr(event, "group_id")


def _event_message_id(event: object) -> str | None:
    getter = getattr(event, "get_message_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and str(value).strip():
            return str(value).strip()
    return _string_attr(event, "message_id")


def _id_value(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


def _message_id_value(message_id: str) -> int | str:
    return _id_value(message_id)


def _emoji_id_for_reaction(reaction: QQReaction) -> str:
    emoji_ids: dict[QQReaction, str] = {"like": _ONEBOT_LIKE_EMOJI_ID}
    return emoji_ids[reaction]


async def _call_onebot_api(
    bot: "Bot",
    api: str,
    **data: object,
) -> QQActionResult:
    call_api = getattr(bot, "call_api", None)
    if not callable(call_api):
        return QQActionResult.unsupported("platform_api_unavailable")
    try:
        await cast("Callable[..., Awaitable[object]]", call_api)(api, **data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("QQ tools OneBot API {} failed: {}", api, exc)
        return QQActionResult.failed("platform_operation_failed")
    return QQActionResult.succeeded()


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
