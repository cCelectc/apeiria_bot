# ruff: noqa: ARG002
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, cast

from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger

FeedbackKind = Literal["success", "failure"]


def _adapter_name(bot: Bot) -> str:
    with suppress(Exception):
        return bot.adapter.get_name().split(maxsplit=1)[0].lower()
    return ""


def _string_attr(obj: object, name: str) -> str | None:
    with suppress(Exception):
        value = getattr(obj, name, None)
        if value is not None:
            return str(value)
    return None


def _nested_string_attr(obj: object, *names: str) -> str | None:
    for name in names:
        obj = getattr(obj, name, None) if obj is not None else None
    if obj is not None:
        return str(obj)
    return None


def _event_message_id(event: Event) -> str | None:
    with suppress(Exception):
        mid = event.get_message_id()  # pyright: ignore[reportAttributeAccessIssue]
        if mid is not None:
            return str(mid)
    return _string_attr(event, "message_id")


def _message_id_value(message_id: str) -> int | str:
    try:
        return int(message_id)
    except (TypeError, ValueError):
        return message_id


@dataclass(frozen=True, slots=True)
class RevokeTarget:
    message_id: str
    author_id: str | None = None


class RevokeActionResult:
    __slots__ = ("reason", "success")

    def __init__(self, *, success: bool = False, reason: str = "") -> None:
        self.success = success
        self.reason = reason

    @classmethod
    def ok(cls) -> "RevokeActionResult":
        return cls(success=True)

    @classmethod
    def failed(cls, reason: str = "operation_failed") -> "RevokeActionResult":
        return cls(success=False, reason=reason)

    @classmethod
    def unsupported(cls, reason: str = "unsupported") -> "RevokeActionResult":
        return cls(success=False, reason=reason)


class SelfRevokeProvider(Protocol):
    def supports(self, bot: Bot, event: Event) -> bool: ...

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None: ...

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool: ...

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult: ...

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult: ...

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult: ...


_revoke_providers: list[SelfRevokeProvider] = []


def _register_provider(provider: SelfRevokeProvider) -> None:
    _revoke_providers.append(provider)


def _resolve_provider(bot: Bot, event: Event) -> SelfRevokeProvider | None:
    for provider in _revoke_providers:
        with suppress(Exception):
            if provider.supports(bot, event):
                return provider
    return None


async def _call_api(bot: Bot, api: str, **data: object) -> RevokeActionResult:
    try:
        await bot.call_api(api, **data)
        return RevokeActionResult.ok()
    except Exception as exc:  # noqa: BLE001
        return RevokeActionResult.failed(str(exc))


# -- OneBot V11 provider --

_ONEBOT_V11 = "onebotv11"
_ONEBOT_SUCCESS_EMOJI = "124"
_ONEBOT_FAILURE_EMOJI = "424"


class OneBotV11RevokeProvider:
    _EMOJI_MAP: ClassVar[dict[FeedbackKind, str]] = {
        "success": _ONEBOT_SUCCESS_EMOJI,
        "failure": _ONEBOT_FAILURE_EMOJI,
    }

    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _ONEBOT_V11:
            return False
        return hasattr(event, "reply") and hasattr(event, "message_id")

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None
        message_id = _string_attr(reply, "message_id")
        if message_id is None:
            return None
        author_id = None
        sender = getattr(reply, "sender", None)
        if sender is not None:
            author_id = _string_attr(sender, "user_id")
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
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
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        return await _call_api(
            bot,
            "delete_msg",
            message_id=_message_id_value(target.message_id),
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(
            bot,
            "delete_msg",
            message_id=_message_id_value(message_id),
        )

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        emoji_id = self._EMOJI_MAP[kind]
        return await _call_api(
            bot,
            "set_msg_emoji_like",
            message_id=_message_id_value(message_id),
            emoji_id=emoji_id,
        )


_register_provider(OneBotV11RevokeProvider())

# -- OneBot V12 provider --

_ONEBOT_V12 = "onebotv12"


class OneBotV12RevokeProvider:
    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _ONEBOT_V12:
            return False
        return hasattr(event, "reply") and hasattr(event, "message_id")

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
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
        self, bot: Bot, event: Event, target: RevokeTarget
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
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        return await _call_api(bot, "delete_message", message_id=target.message_id)

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(bot, "delete_message", message_id=message_id)

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(OneBotV12RevokeProvider())

# -- Telegram provider --

_TELEGRAM = "telegram"


class TelegramRevokeProvider:
    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _TELEGRAM:
            return False
        reply = getattr(event, "reply_to_message", None)
        return (
            reply is not None
            and _string_attr(reply, "message_id") is not None
            and _nested_string_attr(reply, "from_", "id") is not None
            and _nested_string_attr(event, "chat", "id") is not None
            and _string_attr(event, "message_id") is not None
        )

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply_to_message", None)
        if reply is None:
            return None
        message_id = _string_attr(reply, "message_id")
        author_id = _nested_string_attr(reply, "from_", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool:
        bot_id_raw = getattr(bot, "self_id", None)
        if bot_id_raw is None:
            return False
        bot_id = str(bot_id_raw)
        return (
            target.author_id is not None
            and bot_id is not None
            and target.author_id == bot_id
        )

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        chat_id = _nested_string_attr(event, "chat", "id")
        if chat_id is None:
            return RevokeActionResult.unsupported("chat_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            chat_id=_message_id_value(chat_id),
            message_id=_message_id_value(target.message_id),
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        chat_id = _nested_string_attr(event, "chat", "id")
        message_id = _event_message_id(event)
        if chat_id is None:
            return RevokeActionResult.unsupported("chat_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            chat_id=_message_id_value(chat_id),
            message_id=_message_id_value(message_id),
        )

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(TelegramRevokeProvider())

# -- Discord provider --

_DISCORD = "discord"


class DiscordRevokeProvider:
    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _DISCORD:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "id") is not None
            and _nested_string_attr(reply, "author", "id") is not None
            and _string_attr(event, "channel_id") is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None
        message_id = _string_attr(reply, "id")
        author_id = _nested_string_attr(reply, "author", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool:
        bot_ids = {
            str(item).strip()
            for item in (
                getattr(bot, "self_id", None),
                _nested_string_attr(bot, "self_info", "id"),
            )
            if item is not None and str(item).strip()
        }
        return target.author_id is not None and target.author_id in bot_ids

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        message_id = _event_message_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(DiscordRevokeProvider())

# -- Feishu provider --

_FEISHU = "feishu"


class FeishuRevokeProvider:
    def _bot_app_id(self, bot: Bot) -> str | None:
        return _nested_string_attr(bot, "bot_config", "app_id") or _string_attr(
            bot, "self_id"
        )

    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _FEISHU:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "message_id") is not None
            and _nested_string_attr(reply, "sender", "id") is not None
            and _nested_string_attr(reply, "sender", "id_type") is not None
            and self._bot_app_id(bot) is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None
        message_id = _string_attr(reply, "message_id")
        author_id = _nested_string_attr(reply, "sender", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool:
        reply = getattr(event, "reply", None)
        sender_type = _nested_string_attr(reply, "sender", "id_type")
        bot_app_id = self._bot_app_id(bot)
        return (
            sender_type == "app_id"
            and target.author_id is not None
            and bot_app_id is not None
            and target.author_id == bot_app_id
        )

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        return await _call_api(
            bot, f"im/v1/messages/{target.message_id}", method="DELETE"
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        message_id = _event_message_id(event)
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(bot, f"im/v1/messages/{message_id}", method="DELETE")

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(FeishuRevokeProvider())

# -- Satori provider --

_SATORI = "satori"


class SatoriRevokeProvider:
    def _channel_id(self, event: Event) -> str | None:
        return _nested_string_attr(event, "channel", "id")

    def _bot_user_id(self, bot: Bot) -> str | None:
        getter = getattr(bot, "get_self_id", None)
        if callable(getter):
            with suppress(Exception):
                value = getter()
                if value is not None and str(value).strip():
                    return str(value).strip()
        return _nested_string_attr(bot, "self_info", "id")

    def _reply_message_id(self, reply: object) -> str | None:
        data = getattr(reply, "data", None)
        if data is not None:
            with suppress(Exception):
                mid = data.get("id")  # type: ignore[union-attr]
                if mid:
                    return str(mid)
        return _string_attr(reply, "id")

    def _reply_author_id(self, reply: object) -> str | None:
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
        data = getattr(author, "data", None)
        if data is not None:
            with suppress(Exception):
                aid = data.get("id")  # type: ignore[union-attr]
                if aid:
                    return str(aid)
        return _string_attr(author, "id")

    async def _fetch_author_id(
        self, bot: Bot, event: Event, message_id: str | None
    ) -> str | None:
        channel_id = self._channel_id(event)
        if message_id is None or channel_id is None:
            return None
        call_api = getattr(bot, "call_api", None)
        if not callable(call_api):
            return None
        try:
            message = await cast("Callable[..., Awaitable[object]]", call_api)(
                "message_get",
                channel_id=channel_id,
                message_id=message_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("撤回 Satori message_get 失败: {}", exc)
            return None
        return _nested_string_attr(message, "user", "id")

    def _msg_id(self, event: Event) -> str | None:
        return (
            _string_attr(event, "msg_id")
            or _nested_string_attr(event, "message", "id")
            or _event_message_id(event)
        )

    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _SATORI:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and self._reply_message_id(reply) is not None
            and self._bot_user_id(bot) is not None
            and self._channel_id(event) is not None
            and self._msg_id(event) is not None
        )

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None
        message_id = self._reply_message_id(reply)
        if message_id is None:
            return None
        author_id = self._reply_author_id(reply) or (
            await self._fetch_author_id(bot, event, message_id)
        )
        if author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool:
        bot_id_set = {
            str(item).strip()
            for item in (self._bot_user_id(bot),)
            if item is not None and str(item).strip()
        }
        return target.author_id is not None and target.author_id in bot_id_set

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        channel_id = self._channel_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_api(
            bot,
            "message_delete",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        channel_id = self._channel_id(event)
        message_id = self._msg_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(
            bot,
            "message_delete",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(SatoriRevokeProvider())

# -- QQ Guild provider --

_QQ = "qq"


class QQGuildRevokeProvider:
    def _event_type_name(self, event: Event) -> str:
        value = getattr(event, "__type__", None)
        if value is None:
            return ""
        name = getattr(value, "value", value)
        return str(name).lower()

    def supports(self, bot: Bot, event: Event) -> bool:
        if _adapter_name(bot) != _QQ:
            return False
        if self._event_type_name(event) == "direct_message_create":
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _string_attr(reply, "id") is not None
            and _nested_string_attr(reply, "author", "id") is not None
            and _string_attr(event, "channel_id") is not None
            and _event_message_id(event) is not None
        )

    async def get_reply_target(self, bot: Bot, event: Event) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None
        message_id = _string_attr(reply, "id")
        author_id = _nested_string_attr(reply, "author", "id")
        if message_id is None or author_id is None:
            return None
        return RevokeTarget(message_id=message_id, author_id=author_id)

    async def is_bot_authored(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> bool:
        bot_ids = {
            str(item).strip()
            for item in (
                getattr(bot, "self_id", None),
                _nested_string_attr(bot, "self_info", "id"),
            )
            if item is not None and str(item).strip()
        }
        return target.author_id is not None and target.author_id in bot_ids

    async def revoke_message(
        self, bot: Bot, event: Event, target: RevokeTarget
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            channel_id=channel_id,
            message_id=target.message_id,
        )

    async def revoke_trigger_message(
        self, bot: Bot, event: Event
    ) -> RevokeActionResult:
        channel_id = _string_attr(event, "channel_id")
        message_id = _event_message_id(event)
        if channel_id is None:
            return RevokeActionResult.unsupported("channel_id_missing")
        if message_id is None:
            return RevokeActionResult.unsupported("trigger_message_id_missing")
        return await _call_api(
            bot,
            "delete_message",
            channel_id=channel_id,
            message_id=message_id,
        )

    async def apply_feedback(
        self, bot: Bot, event: Event, *, kind: FeedbackKind
    ) -> RevokeActionResult:
        return RevokeActionResult.unsupported("reaction_feedback_unsupported")


_register_provider(QQGuildRevokeProvider())
