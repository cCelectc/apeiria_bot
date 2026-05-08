"""Normalize adapter event payloads into conversation-friendly fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nonebot.adapters import Event

    from apeiria.conversation.models import MessageKind

_MEDIA_TYPES = {"image", "img", "audio", "record", "video", "file"}
_SAFE_MEDIA_KEYS = (
    "url",
    "asset_id",
    "file",
    "path",
    "mime",
    "mime_type",
    "alt",
    "width",
    "height",
    "size",
    "duration",
    "file_name",
    "name",
)
_SAFE_ADAPTER_SEGMENT_KEYS = (
    "id",
    "message_id",
    "user_id",
    "target_id",
    "group_id",
    "channel_id",
    "guild_id",
    "role_id",
    "name",
    "title",
    "value",
    "text",
    "alt",
)


def extract_platform_message_id(
    event: "Event",
    raw_data: dict[str, Any] | None,
) -> str | None:
    getter = getattr(event, "get_message_id", None)
    if callable(getter):
        try:
            value = getter()
            if value is not None:
                return str(value)
        except Exception:  # noqa: BLE001
            pass
    if not raw_data:
        return None
    for key in ("message_id", "id"):
        value = raw_data.get(key)
        if value is not None:
            return str(value)
    return None


def extract_platform_reply_id(raw_data: dict[str, Any] | None) -> str | None:
    if not raw_data:
        return None
    reply = raw_data.get("reply")
    if isinstance(reply, dict):
        for key in ("message_id", "id"):
            value = reply.get(key)
            if value is not None:
                return str(value)
    return None


def extract_author_name(raw_data: dict[str, Any] | None) -> str | None:
    if not raw_data:
        return None
    sender = raw_data.get("sender")
    if isinstance(sender, dict):
        for key in ("card", "nickname", "name"):
            value = sender.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("user_name", "nickname", "name"):
        value = raw_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def detect_has_media(raw_data: dict[str, Any] | None) -> bool:
    if not raw_data:
        return False
    message = raw_data.get("message")
    if isinstance(message, list):
        for segment in message:
            if isinstance(segment, dict):
                seg_type = segment.get("type")
                if isinstance(seg_type, str) and seg_type in _MEDIA_TYPES:
                    return True
    return False


def resolve_message_kind(*, text_content: str, has_media: bool) -> MessageKind:
    has_text = bool(text_content.strip())
    if has_text and has_media:
        return "mixed"
    if has_media:
        return "media"
    return "text"


def build_normalized_content(  # noqa: C901, PLR0912
    *,
    raw_data: dict[str, Any] | None,
    text_content: str,
    adapter: str | None = None,
) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    if text_content.strip():
        segments.append({"type": "text", "text": text_content.strip()})

    mentioned_user_ids: list[str] = []
    quoted_text: str | None = None
    if raw_data:
        reply = raw_data.get("reply")
        if isinstance(reply, dict):
            for key in ("text", "message", "content"):
                value = reply.get(key)
                if isinstance(value, str) and value.strip():
                    quoted_text = value.strip()
                    break
        message = raw_data.get("message")
        if isinstance(message, list):
            for segment in message:
                if not isinstance(segment, dict):
                    continue
                seg_type = segment.get("type")
                data = segment.get("data")
                if not isinstance(seg_type, str):
                    continue
                if seg_type == "at" and isinstance(data, dict):
                    qq = data.get("qq")
                    if qq is not None:
                        mentioned_user_ids.append(str(qq))
                elif seg_type in _MEDIA_TYPES:
                    segments.append(
                        _build_media_segment(
                            seg_type,
                            data,
                            adapter=adapter,
                        )
                    )
                else:
                    adapter_segment = _build_adapter_segment(
                        adapter=adapter,
                        segment_type=seg_type,
                        data=data,
                    )
                    if adapter_segment is not None:
                        segments.append(adapter_segment)

    payload: dict[str, Any] = {
        "segments": segments,
        "plain_text": text_content,
        "mentioned_user_ids": mentioned_user_ids,
    }
    if quoted_text:
        payload["quoted_text"] = quoted_text
    return payload


def build_debug_raw_payload(
    raw_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not raw_data:
        return None

    payload: dict[str, Any] = {}
    for key in (
        "message_id",
        "id",
        "time",
        "self_id",
        "user_id",
        "group_id",
        "post_type",
        "message_type",
        "sub_type",
        "notice_type",
        "request_type",
    ):
        value = raw_data.get(key)
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value

    sender = raw_data.get("sender")
    sender_summary = build_mapping_summary(
        sender,
        allowed_keys=("user_id", "nickname", "card", "name", "role"),
    )
    if sender_summary:
        payload["sender"] = sender_summary

    reply = raw_data.get("reply")
    reply_summary = build_mapping_summary(
        reply,
        allowed_keys=("message_id", "id", "user_id", "text"),
    )
    if reply_summary:
        payload["reply"] = reply_summary

    message = raw_data.get("message")
    if isinstance(message, list):
        segment_types = [
            seg_type
            for segment in message
            if isinstance(segment, Mapping)
            and isinstance((seg_type := segment.get("type")), str)
            and seg_type.strip()
        ]
        if segment_types:
            payload["message_segment_types"] = segment_types[:20]

    return payload or None


def build_mapping_summary(
    value: object,
    *,
    allowed_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    summary = {
        key: item
        for key in allowed_keys
        if isinstance((item := value.get(key)), (str, int, float, bool))
    }
    return summary or None


def _build_media_segment(
    seg_type: str,
    data: object,
    *,
    adapter: str | None,
) -> dict[str, Any]:
    segment: dict[str, Any] = {"type": seg_type}
    if not isinstance(data, Mapping):
        if adapter and seg_type in {"audio", "record"}:
            segment["adapter"] = adapter
            segment["unsupported_reason"] = "missing_safe_reference"
        return segment

    for key in _SAFE_MEDIA_KEYS:
        value = data.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            segment[key] = value
    if adapter and seg_type in {"audio", "record"}:
        segment["adapter"] = adapter
        if not _has_safe_media_reference(segment):
            segment["unsupported_reason"] = "missing_safe_reference"
    return segment


def _has_safe_media_reference(segment: Mapping[str, Any]) -> bool:
    return any(
        isinstance(segment.get(key), str) and str(segment.get(key)).strip()
        for key in ("url", "asset_id", "file", "path")
    )


def _build_adapter_segment(
    *,
    adapter: str | None,
    segment_type: str,
    data: object,
) -> dict[str, Any] | None:
    if not segment_type.strip():
        return None

    segment: dict[str, Any] = {
        "type": "adapter",
        "segment_type": segment_type,
    }
    if adapter:
        segment["adapter"] = adapter

    safe_data = build_mapping_summary(data, allowed_keys=_SAFE_ADAPTER_SEGMENT_KEYS)
    if safe_data:
        segment["data"] = safe_data
    return segment


__all__ = [
    "build_debug_raw_payload",
    "build_mapping_summary",
    "build_normalized_content",
    "detect_has_media",
    "extract_author_name",
    "extract_platform_message_id",
    "extract_platform_reply_id",
    "resolve_message_kind",
]
