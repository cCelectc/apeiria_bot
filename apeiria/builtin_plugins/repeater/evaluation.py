from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import log1p
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .state import ContentKey, ContentSegment, SkipReason

IGNORED_COMMAND_PREFIX = "/"

SUPPORTED_TEXT_TYPES = frozenset({"text", "plain"})
SUPPORTED_EMOJI_TYPES = frozenset({"emoji", "face", "mface", "market_face", "sticker"})
SUPPORTED_IMAGE_TYPES = frozenset({"image", "picture", "photo"})
UNSUPPORTED_SEGMENT_TYPES = frozenset(
    {
        "reply",
        "forward",
        "node",
        "json",
        "xml",
        "card",
        "markdown",
    }
)
EMOJI_ID_KEYS = ("id", "emoji_id", "face_id", "file_id")
IMAGE_ID_KEYS = ("file_id", "file", "id", "image_id", "uuid", "md5")


@dataclass(frozen=True, slots=True)
class ContentKeyResult:
    status: Literal["supported", "unsupported"]
    key: ContentKey | None = None
    reason: SkipReason = "unsupported_message"


def build_content_key(
    message: object,
) -> ContentKeyResult:
    segments = tuple(iter_message_segments(message))
    segments = segments or _text_segments_from_message(message)
    if not segments:
        return ContentKeyResult(status="unsupported")

    if message_starts_with_ignored_prefix(segments):
        return ContentKeyResult(status="unsupported", reason="ignored_prefix")

    key_parts = tuple(
        _content_segment(segment_type, data) for segment_type, data in segments
    )
    if any(part is None for part in key_parts):
        return ContentKeyResult(status="unsupported")

    if not key_parts:
        return ContentKeyResult(status="unsupported")
    return ContentKeyResult(
        status="supported",
        key=tuple(part for part in key_parts if part is not None),
    )


def iter_message_segments(
    message: object,
) -> Iterable[tuple[str, Mapping[str, object]]]:
    if isinstance(message, str):
        return ()

    if isinstance(message, Mapping):
        segment = _segment_from_object(message)
        return (segment,) if segment is not None else ()

    if isinstance(message, Iterable):
        return tuple(
            segment
            for item in message
            if (segment := _segment_from_object(item)) is not None
        )

    segment = _segment_from_object(message)
    return (segment,) if segment is not None else ()


def message_starts_with_ignored_prefix(
    segments: Sequence[tuple[str, Mapping[str, object]]],
) -> bool:
    if not segments:
        return False
    first_type, first_data = segments[0]
    if first_type.strip().lower() not in SUPPORTED_TEXT_TYPES:
        return False
    text = str(first_data.get("text", ""))
    return text.startswith(IGNORED_COMMAND_PREFIX)


def repeat_probability(
    count: int,
    *,
    repeat_threshold: int,
    base_probability: float,
    max_probability: float,
    saturation_extra: int,
) -> float:
    if count < repeat_threshold:
        return 0.0
    extra = count - repeat_threshold
    if extra <= 0:
        return base_probability
    progress = min(1.0, log1p(extra) / log1p(saturation_extra))
    return base_probability + (max_probability - base_probability) * progress


def _segment_from_object(
    value: object,
) -> tuple[str, Mapping[str, object]] | None:
    if isinstance(value, Mapping):
        raw_type = value.get("type")
        raw_data = value.get("data", {})
    else:
        raw_type = getattr(value, "type", None)
        raw_data = getattr(value, "data", {})

    if not isinstance(raw_type, str):
        return None
    data = dict(raw_data) if isinstance(raw_data, Mapping) else {}
    return raw_type, data


def _string_message_text(message: object) -> str | None:
    if isinstance(message, str):
        return message
    return None


def _text_segments_from_message(
    message: object,
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    text = _string_message_text(message)
    if text is None:
        return ()
    return (("text", {"text": text}),)


def _content_segment(
    segment_type: str,
    data: Mapping[str, object],
) -> ContentSegment | None:
    normalized_type = segment_type.strip().lower()
    if normalized_type in UNSUPPORTED_SEGMENT_TYPES:
        return None
    if normalized_type in SUPPORTED_TEXT_TYPES:
        return "text", str(data.get("text", ""))
    if normalized_type in SUPPORTED_EMOJI_TYPES:
        return _stable_segment("emoji", data, EMOJI_ID_KEYS)
    if normalized_type in SUPPORTED_IMAGE_TYPES:
        return _stable_segment("image", data, IMAGE_ID_KEYS)
    return None


def _stable_segment(
    kind: str,
    data: Mapping[str, object],
    keys: tuple[str, ...],
) -> ContentSegment | None:
    stable_id = _first_stable_value(data, keys)
    if stable_id is None:
        return None
    return kind, stable_id


def _first_stable_value(
    data: Mapping[str, object],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


__all__ = [
    "IGNORED_COMMAND_PREFIX",
    "ContentKeyResult",
    "build_content_key",
    "iter_message_segments",
    "message_starts_with_ignored_prefix",
    "repeat_probability",
]
