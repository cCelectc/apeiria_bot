from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from ._helpers import (
    _TELEGRAM_ADAPTER_NAME,
    _call_adapter_api,
    _event_message_id,
    _message_id_value,
    _nested_string_attr,
    _normalized_adapter_name,
    _string_attr,
    _target_matches_bot_id,
)
from ._types import FeedbackKind, RevokeActionResult, RevokeTarget


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
