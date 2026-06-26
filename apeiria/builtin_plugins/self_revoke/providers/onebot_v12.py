from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from ._helpers import (
    _ONEBOT_V12_ADAPTER_NAME,
    _call_onebot_api,
    _event_message_id,
    _nested_string_attr,
    _normalized_adapter_name,
    _string_attr,
)
from ._types import FeedbackKind, RevokeActionResult, RevokeTarget


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
