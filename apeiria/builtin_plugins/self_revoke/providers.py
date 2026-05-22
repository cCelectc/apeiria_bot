from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from nonebot.log import logger

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

FeedbackKind = Literal["success", "failure"]
ActionStatus = Literal["success", "failed", "unsupported"]

_ONEBOT_SUCCESS_REACTION_EMOJI_ID = "124"
_ONEBOT_FAILURE_REACTION_EMOJI_ID = "424"  # QFace marker for failure feedback.


@dataclass(frozen=True, slots=True)
class RevokeTarget:
    """Provider-neutral reference to one platform message."""

    message_id: str
    author_id: str | None = None


@dataclass(frozen=True, slots=True)
class RevokeActionResult:
    """Result for best-effort platform operations."""

    status: ActionStatus
    reason: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    @classmethod
    def succeeded(cls) -> "RevokeActionResult":
        return cls(status="success")

    @classmethod
    def failed(cls, reason: str = "operation_failed") -> "RevokeActionResult":
        return cls(status="failed", reason=reason)

    @classmethod
    def unsupported(cls, reason: str = "unsupported") -> "RevokeActionResult":
        return cls(status="unsupported", reason=reason)


class SelfRevokeProvider(Protocol):
    """Adapter capability boundary consumed by the self-revoke plugin."""

    def supports(self, bot: "Bot", event: "Event") -> bool: ...

    async def get_reply_target(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeTarget | None: ...

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> bool: ...

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult: ...

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult: ...

    async def apply_feedback(
        self,
        bot: "Bot",
        event: "Event",
        *,
        kind: FeedbackKind,
    ) -> RevokeActionResult: ...


class SelfRevokeProviderRegistry:
    """Resolve the first provider that supports a bot/event pair."""

    def __init__(self, providers: tuple[SelfRevokeProvider, ...]) -> None:
        self._providers = providers

    def resolve(
        self,
        bot: "Bot",
        event: "Event",
    ) -> SelfRevokeProvider | None:
        for provider in self._providers:
            provider_supported = self._provider_supports(provider, bot, event)
            if provider_supported:
                return provider
        return None

    def _provider_supports(
        self,
        provider: SelfRevokeProvider,
        bot: "Bot",
        event: "Event",
    ) -> bool:
        try:
            return provider.supports(bot, event)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Self-revoke provider support check failed: {}",
                exc,
            )
            return False


class OneBotSelfRevokeProvider:
    """Initial OneBot provider for message revoke and best-effort reactions."""

    _REACTION_EMOJI_BY_KIND: ClassVar[dict[FeedbackKind, str]] = {
        "success": _ONEBOT_SUCCESS_REACTION_EMOJI_ID,
        "failure": _ONEBOT_FAILURE_REACTION_EMOJI_ID,
    }

    def supports(self, bot: "Bot", event: "Event") -> bool:
        adapter_name = str(getattr(bot, "type", "") or "").lower()
        if "onebot" not in adapter_name.replace(" ", ""):
            return False
        return hasattr(event, "reply") or hasattr(event, "message_id")

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _string_attr(reply, "message_id")
        if message_id is None:
            return None

        author_id: str | None = None
        sender = getattr(reply, "sender", None)
        if sender is not None:
            author_id = _string_attr(sender, "user_id")
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> bool:
        bot_ids = {
            str(item)
            for item in (
                getattr(bot, "self_id", None),
                getattr(event, "self_id", None),
            )
            if item is not None
        }
        return target.author_id is not None and target.author_id in bot_ids

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> RevokeActionResult:
        return await _call_onebot_api(
            bot,
            "delete_msg",
            message_id=_message_id_value(target.message_id),
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_onebot_api(
            bot,
            "delete_msg",
            message_id=_message_id_value(message_id),
        )

    async def apply_feedback(
        self,
        bot: "Bot",
        event: "Event",
        *,
        kind: FeedbackKind,
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        emoji_id = self._REACTION_EMOJI_BY_KIND[kind]
        return await _call_onebot_api(
            bot,
            "set_msg_emoji_like",
            message_id=_message_id_value(message_id),
            emoji_id=emoji_id,
        )


def _string_attr(value: object, name: str) -> str | None:
    item = getattr(value, name, None)
    if item is None:
        return None
    text = str(item).strip()
    return text or None


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


def _message_id_value(message_id: str) -> int | str:
    try:
        return int(message_id)
    except ValueError:
        return message_id


async def _call_onebot_api(
    bot: "Bot",
    api: str,
    **data: object,
) -> RevokeActionResult:
    try:
        await bot.call_api(api, **data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Self-revoke OneBot API {} failed: {}", api, exc)
        return RevokeActionResult.failed("platform_operation_failed")
    return RevokeActionResult.succeeded()


self_revoke_provider_registry = SelfRevokeProviderRegistry(
    providers=(OneBotSelfRevokeProvider(),)
)


__all__ = [
    "FeedbackKind",
    "OneBotSelfRevokeProvider",
    "RevokeActionResult",
    "RevokeTarget",
    "SelfRevokeProvider",
    "SelfRevokeProviderRegistry",
    "self_revoke_provider_registry",
]
