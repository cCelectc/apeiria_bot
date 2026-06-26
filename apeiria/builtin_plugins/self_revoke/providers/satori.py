from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

from ._helpers import (
    _SATORI_ADAPTER_NAME,
    _call_adapter_api,
    _normalized_adapter_name,
    _satori_bot_user_id,
    _satori_channel_id,
    _satori_event_message_id,
    _satori_fetch_author_id,
    _satori_reply_author_id,
    _satori_reply_message_id,
    _target_matches_bot_id,
)
from ._types import FeedbackKind, RevokeActionResult, RevokeTarget


class SatoriSelfRevokeProvider:
    """Satori provider for quote targets that include author metadata."""

    def supports(self, bot: "Bot", event: "Event") -> bool:
        if _normalized_adapter_name(bot) != _SATORI_ADAPTER_NAME:
            return False
        reply = getattr(event, "reply", None)
        return (
            reply is not None
            and _satori_reply_message_id(reply) is not None
            and _satori_bot_user_id(bot) is not None
            and _satori_channel_id(event) is not None
            and _satori_event_message_id(event) is not None
        )

    async def get_reply_target(
        self,
        bot: "Bot",
        event: "Event",
    ) -> RevokeTarget | None:
        reply = getattr(event, "reply", None)
        if reply is None:
            return None

        message_id = _satori_reply_message_id(reply)
        if message_id is None:
            return None
        author_id = _satori_reply_author_id(reply) or await _satori_fetch_author_id(
            bot,
            event,
            message_id,
        )
        if author_id is None:
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
