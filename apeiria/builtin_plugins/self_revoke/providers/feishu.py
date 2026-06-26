from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from ._helpers import (
    _FEISHU_ADAPTER_NAME,
    _call_adapter_api,
    _event_message_id,
    _feishu_bot_app_id,
    _nested_string_attr,
    _normalized_adapter_name,
    _string_attr,
)
from ._types import FeedbackKind, RevokeActionResult, RevokeTarget


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
