from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol

from nonebot.log import logger

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

FeedbackKind = Literal["success", "failure"]
ActionStatus = Literal["success", "failed", "unsupported"]

_ONEBOT_SUCCESS_REACTION_EMOJI_ID = "124"
_ONEBOT_FAILURE_REACTION_EMOJI_ID = "424"  # QFace marker for failure feedback.
_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_ONEBOT_V12_ADAPTER_NAME = "onebotv12"
_TELEGRAM_ADAPTER_NAME = "telegram"
_DISCORD_ADAPTER_NAME = "discord"
_QQ_ADAPTER_NAME = "qq"
_FEISHU_ADAPTER_NAME = "feishu"
_SATORI_ADAPTER_NAME = "satori"


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


class OneBotV11SelfRevokeProvider:
    """OneBot v11 provider for message revoke and best-effort reactions."""

    _REACTION_EMOJI_BY_KIND: ClassVar[dict[FeedbackKind, str]] = {
        "success": _ONEBOT_SUCCESS_REACTION_EMOJI_ID,
        "failure": _ONEBOT_FAILURE_REACTION_EMOJI_ID,
    }

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _ONEBOT_V11_ADAPTER_NAME:
            return False
        return hasattr(event, "reply") and hasattr(event, "message_id")

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


class OneBotV12SelfRevokeProvider:
    """OneBot v12 provider for message revoke operations."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _ONEBOT_V12_ADAPTER_NAME:
            return False
        return hasattr(event, "reply") and hasattr(event, "message_id")

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

        return RevokeTarget(
            message_id=message_id,
            author_id=_string_attr(reply, "user_id"),
        )

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> bool:
        bot_self_id = _string_attr(bot, "self_id")
        event_self_id = _nested_string_attr(event, "self", "user_id")
        return (
            target.author_id is not None
            and bot_self_id is not None
            and event_self_id is not None
            and bot_self_id == event_self_id == target.author_id
        )

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> RevokeActionResult:
        return await _call_onebot_api(
            bot,
            "delete_message",
            message_id=target.message_id,
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
            "delete_message",
            message_id=message_id,
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


class TelegramSelfRevokeProvider:
    """Telegram provider for reply-target message deletion."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _TELEGRAM_ADAPTER_NAME:
            return False
        reply = getattr(event, "reply_to_message", None)
        return (
            reply is not None
            and _string_attr(reply, "message_id") is not None
            and _nested_string_attr(reply, "from_", "id") is not None
            and _nested_string_attr(event, "chat", "id") is not None
            and _string_attr(event, "message_id") is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply_to_message", None)
        if reply is None:
            return None

        message_id = _string_attr(reply, "message_id")
        author_id = _nested_string_attr(reply, "from_", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> bool:
        return _target_matches_bot_id(target, (getattr(bot, "self_id", None),))

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult:
        chat_id = _nested_string_attr(event, "chat", "id")
        if chat_id is None:
            return RevokeActionResult.unsupported("chat_id_missing")
        return await _call_adapter_api(
            bot,
            _TELEGRAM_ADAPTER_NAME,
            "delete_message",
            chat_id=_message_id_value(chat_id),
            message_id=_message_id_value(target.message_id),
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        chat_id = _nested_string_attr(event, "chat", "id")
        message_id = _event_message_id(event)
        if chat_id is None:
            return RevokeActionResult.unsupported("chat_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_adapter_api(
            bot,
            _TELEGRAM_ADAPTER_NAME,
            "delete_message",
            chat_id=_message_id_value(chat_id),
            message_id=_message_id_value(message_id),
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


class DiscordSelfRevokeProvider:
    """Discord provider for reply-target message deletion."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _DISCORD_ADAPTER_NAME:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "id") is not None
            and _nested_string_attr(reply, "author", "id") is not None
            and _string_attr(event, "channel_id") is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _string_attr(reply, "id")
        author_id = _nested_string_attr(reply, "author", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> bool:
        return _target_matches_bot_id(
            target,
            (
                getattr(bot, "self_id", None),
                _nested_string_attr(bot, "self_info", "id"),
            ),
        )

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_adapter_api(
            bot,
            _DISCORD_ADAPTER_NAME,
            "delete_message",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        message_id = _event_message_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_adapter_api(
            bot,
            _DISCORD_ADAPTER_NAME,
            "delete_message",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


class FeishuSelfRevokeProvider:
    """Feishu provider for reply-target message deletion."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _FEISHU_ADAPTER_NAME:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "message_id") is not None
            and _nested_string_attr(reply, "sender", "id") is not None
            and _nested_string_attr(reply, "sender", "id_type") is not None
            and _feishu_bot_app_id(bot) is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _string_attr(reply, "message_id")
        author_id = _nested_string_attr(reply, "sender", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> bool:
        reply = getattr(event, "reply", None)
        sender_type = _nested_string_attr(reply, "sender", "id_type")
        bot_app_id = _feishu_bot_app_id(bot)
        return (
            sender_type == "app_id"
            and target.author_id is not None
            and bot_app_id is not None
            and target.author_id == bot_app_id
        )

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> RevokeActionResult:
        return await _call_adapter_api(
            bot,
            _FEISHU_ADAPTER_NAME,
            f"im/v1/messages/{target.message_id}",
            method="DELETE",
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_adapter_api(
            bot,
            _FEISHU_ADAPTER_NAME,
            f"im/v1/messages/{message_id}",
            method="DELETE",
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


class SatoriSelfRevokeProvider:
    """Satori provider for quote targets that include author metadata."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _SATORI_ADAPTER_NAME:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _satori_reply_message_id(reply) is not None
            and _satori_reply_author_id(reply) is not None
            and _satori_bot_user_id(bot) is not None
            and _satori_channel_id(event) is not None
            and _satori_event_message_id(event) is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _satori_reply_message_id(reply)
        author_id = _satori_reply_author_id(reply)
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> bool:
        return _target_matches_bot_id(target, (_satori_bot_user_id(bot),))

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult:
        channel_id = _satori_channel_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_adapter_api(
            bot,
            _SATORI_ADAPTER_NAME,
            "message_delete",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        channel_id = _satori_channel_id(event)
        message_id = _satori_event_message_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_adapter_api(
            bot,
            _SATORI_ADAPTER_NAME,
            "message_delete",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


class QQGuildSelfRevokeProvider:
    """QQ guild/channel provider for reply-target message deletion."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _QQ_ADAPTER_NAME:
            return False
        if _event_type_name(event) == "direct_message_create":
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "id") is not None
            and _nested_string_attr(reply, "author", "id") is not None
            and _string_attr(event, "channel_id") is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _string_attr(reply, "id")
        author_id = _nested_string_attr(reply, "author", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self,
        bot: "Bot",
        event: "Event",  # noqa: ARG002
        target: RevokeTarget,
    ) -> bool:
        return _target_matches_bot_id(
            target,
            (
                getattr(bot, "self_id", None),
                _nested_string_attr(bot, "self_info", "id"),
            ),
        )

    async def revoke_message(
        self,
        bot: "Bot",
        event: "Event",
        target: RevokeTarget,
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_adapter_api(
            bot,
            _QQ_ADAPTER_NAME,
            "delete_message",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        message_id = _event_message_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_adapter_api(
            bot,
            _QQ_ADAPTER_NAME,
            "delete_message",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self,
        bot: "Bot",  # noqa: ARG002
        event: "Event",  # noqa: ARG002
        *,
        kind: FeedbackKind,  # noqa: ARG002
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


OneBotSelfRevokeProvider = OneBotV11SelfRevokeProvider


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


def _nested_string_attr(value: object, *names: str) -> str | None:
    current = value
    for name in names:
        try:
            current = getattr(current, name, None)
        except Exception:  # noqa: BLE001
            return None
        if current is None:
            return None
    text = str(current).strip()
    return text or None


def _mapping_string_attr(value: object, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    item = value.get(key)
    if item is None:
        return None
    text = str(item).strip()
    return text or None


def _event_type_name(event: object) -> str:
    value = getattr(event, "__type__", None)
    if value is None:
        return ""
    name = getattr(value, "value", value)
    return str(name).lower()


def _target_matches_bot_id(target: RevokeTarget, bot_ids: tuple[object, ...]) -> bool:
    normalized_bot_ids = {
        str(item).strip() for item in bot_ids if item is not None and str(item).strip()
    }
    return target.author_id is not None and target.author_id in normalized_bot_ids


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


def _feishu_bot_app_id(bot: object) -> str | None:
    return _nested_string_attr(bot, "bot_config", "app_id") or _string_attr(
        bot,
        "self_id",
    )


def _satori_bot_user_id(bot: object) -> str | None:
    getter = getattr(bot, "get_self_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and str(value).strip():
            return str(value).strip()
    return _nested_string_attr(bot, "self_info", "id")


def _satori_channel_id(event: object) -> str | None:
    return _nested_string_attr(event, "channel", "id")


def _satori_event_message_id(event: object) -> str | None:
    return (
        _string_attr(event, "msg_id")
        or _nested_string_attr(event, "message", "id")
        or _event_message_id(event)
    )


def _satori_reply_message_id(reply: object) -> str | None:
    return _mapping_string_attr(getattr(reply, "data", None), "id") or _string_attr(
        reply,
        "id",
    )


def _satori_reply_author_id(reply: object) -> str | None:
    children = getattr(reply, "children", None)
    getter = getattr(children, "get", None)
    if not callable(getter):
        return None
    try:
        author_segments = getter("author")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(author_segments, Sequence):
        return None
    try:
        author = author_segments[0]
    except (IndexError, TypeError):
        return None
    return _mapping_string_attr(getattr(author, "data", None), "id") or _string_attr(
        author,
        "id",
    )


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


async def _call_adapter_api(
    bot: "Bot",
    adapter: str,
    api: str,
    **data: object,
) -> RevokeActionResult:
    try:
        await bot.call_api(api, **data)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Self-revoke {} API {} failed: {}", adapter, api, exc)
        return RevokeActionResult.failed("platform_operation_failed")
    return RevokeActionResult.succeeded()


self_revoke_provider_registry = SelfRevokeProviderRegistry(
    providers=(
        OneBotV11SelfRevokeProvider(),
        OneBotV12SelfRevokeProvider(),
        TelegramSelfRevokeProvider(),
        DiscordSelfRevokeProvider(),
        FeishuSelfRevokeProvider(),
        SatoriSelfRevokeProvider(),
        QQGuildSelfRevokeProvider(),
    )
)


__all__ = [
    "DiscordSelfRevokeProvider",
    "FeedbackKind",
    "FeishuSelfRevokeProvider",
    "OneBotSelfRevokeProvider",
    "OneBotV11SelfRevokeProvider",
    "OneBotV12SelfRevokeProvider",
    "QQGuildSelfRevokeProvider",
    "RevokeActionResult",
    "RevokeTarget",
    "SatoriSelfRevokeProvider",
    "SelfRevokeProvider",
    "SelfRevokeProviderRegistry",
    "TelegramSelfRevokeProvider",
    "self_revoke_provider_registry",
]
