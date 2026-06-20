from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.builtin_plugins.message_persist.protocol import ExtractedMessage
from apeiria.builtin_plugins.message_persist.registry import register_extractor

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


class OneBotV11Extractor:
    def supports(self, bot: Bot, _event: Event) -> bool:
        return "onebot" in type(bot).__module__.lower()

    def extract(self, _bot: Bot, event: Event) -> ExtractedMessage | None:
        message = getattr(event, "message", None)
        if message is None:
            return None

        is_bot_message = _is_sent_event(event)

        try:
            user_id = event.get_user_id()
        except (AttributeError, ValueError):
            user_id = ""

        message_id = str(getattr(event, "message_id", "")) or None

        parts: list[str] = []
        plain_parts: list[str] = []
        meta: dict[str, Any] = {}
        pic_count = 0
        emoji_count = 0
        raw_segments: list[dict[str, Any]] = []

        for seg in message:
            seg_type = getattr(seg, "type", "")
            seg_data = dict(getattr(seg, "data", {}))
            raw_segments.append({"type": seg_type, "data": seg_data})

            if seg_type == "text":
                text = seg_data.get("text", "")
                parts.append(text)
                plain_parts.append(text)
            elif seg_type == "image":
                pic_count += 1
                ref = f"Pic:{pic_count}"
                parts.append(f"[{ref}]")
                meta[ref] = {
                    "type": "image",
                    "url": seg_data.get("url", ""),
                    "file": seg_data.get("file", ""),
                }
            elif seg_type in ("face", "emoji"):
                emoji_count += 1
                ref = f"Emoji:{emoji_count}"
                parts.append(f"[{ref}]")
                meta[ref] = {"type": seg_type, "id": seg_data.get("id", "")}
            elif seg_type == "at":
                target = seg_data.get("qq", seg_data.get("user_id", ""))
                parts.append(f"@{target}")
                plain_parts.append(f"@{target}")
            elif seg_type == "reply":
                pass
            else:
                parts.append(f"[{seg_type}]")

        if raw_segments:
            meta["_raw_segments"] = raw_segments

        content = "".join(parts).strip()
        plain_text = "".join(plain_parts).strip()

        return ExtractedMessage(
            content=content,
            plain_text=plain_text,
            user_id=user_id,
            message_id=message_id,
            meta=meta or None,
            is_bot_message=is_bot_message,
        )


def _is_sent_event(event: Event) -> bool:
    event_type = type(event).__name__.lower()
    return "sent" in event_type or "messagesent" in event_type.replace("_", "")


register_extractor(OneBotV11Extractor())
