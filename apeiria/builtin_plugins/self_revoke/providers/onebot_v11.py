from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from ._helpers import (
    _ONEBOT_FAILURE_REACTION_EMOJI_ID,
    _ONEBOT_SUCCESS_REACTION_EMOJI_ID,
    _ONEBOT_V11_ADAPTER_NAME,
    _call_onebot_api,
    _event_message_id,
    _message_id_value,
    _normalized_adapter_name,
    _string_attr,
)
from ._types import FeedbackKind, RevokeActionResult, RevokeTarget


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
