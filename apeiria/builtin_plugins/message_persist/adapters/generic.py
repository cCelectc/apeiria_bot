from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from apeiria.builtin_plugins.message_persist.protocol import ExtractedMessage
from apeiria.builtin_plugins.message_persist.registry import register_extractor

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


class GenericExtractor:
    def supports(self, _bot: Bot, _event: Event) -> bool:
        return True

    def extract(self, _bot: Bot, event: Event) -> ExtractedMessage | None:
        try:
            plain_text = event.get_plaintext().strip()
        except (AttributeError, ValueError):
            plain_text = ""

        if not plain_text:
            message = getattr(event, "message", None)
            if message is not None:
                plain_text = str(message).strip()

        if not plain_text:
            return None

        try:
            user_id = event.get_user_id()
        except (AttributeError, ValueError):
            user_id = ""

        message_id = None
        with contextlib.suppress(AttributeError, ValueError):
            message_id = event.get_message_id()

        meta: dict[str, Any] | None = None
        message = getattr(event, "message", None)
        if message is not None and hasattr(message, "__iter__"):
            raw_segments = []
            for seg in message:
                seg_type = getattr(seg, "type", "unknown")
                seg_data = dict(getattr(seg, "data", {}))
                raw_segments.append({"type": seg_type, "data": seg_data})
            if raw_segments:
                meta = {"_raw_segments": raw_segments}

        is_bot_message = _is_sent_event(event)

        return ExtractedMessage(
            content=plain_text,
            plain_text=plain_text,
            user_id=user_id,
            message_id=message_id,
            meta=meta,
            is_bot_message=is_bot_message,
        )


def _is_sent_event(event: Event) -> bool:
    event_type = type(event).__name__.lower()
    return "sent" in event_type or "messagesent" in event_type.replace("_", "")


register_extractor(GenericExtractor())
