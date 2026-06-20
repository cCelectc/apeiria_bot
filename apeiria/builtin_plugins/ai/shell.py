from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from apeiria.ai.types import PromptFragment

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

_SEG_TAG = "[SEG]"
_SEG_PATTERN = re.compile(re.escape(_SEG_TAG))


def sanitize_input(text: str) -> str:
    return text.replace(_SEG_TAG, "")


def split_segments(text: str) -> list[str]:
    if _SEG_TAG not in text:
        return [text] if text.strip() else []
    parts = text.split(_SEG_TAG)
    return [p.strip() for p in parts if p.strip()]


def strip_seg_tags(text: str) -> str:
    return _SEG_PATTERN.sub("", text).strip()


class StreamingSegmentBuffer:
    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, chunk: str) -> list[str]:
        self._buffer += chunk
        ready: list[str] = []
        while _SEG_TAG in self._buffer:
            before, _, after = self._buffer.partition(_SEG_TAG)
            if before.strip():
                ready.append(before.strip())
            self._buffer = after
        return ready

    def has_partial_tag(self) -> bool:
        return any(self._buffer.endswith(_SEG_TAG[:i]) for i in range(1, len(_SEG_TAG)))

    def flush(self) -> str | None:
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining or None


def build_segmentation_fragment(*, enabled: bool) -> PromptFragment | None:
    if not enabled:
        return None
    return PromptFragment(
        role="system",
        content=(
            "当你的回复包含多个自然段落或话题转换时，"
            "请使用 [SEG] 标签来分隔不同的消息段落。"
            "例如：'你好呀！[SEG]今天天气真不错[SEG]要不要出去走走？' "
            "不要在每句话后都加 [SEG]，只在自然的消息边界处使用。"
        ),
        placement="last",
    )


async def send_reply(
    bot: Bot,
    event: Event,
    reply_text: str,
    *,
    segment_enabled: bool = True,
    segment_delay: float = 1.5,
) -> None:
    if not reply_text or not reply_text.strip():
        return

    from apeiria.conversation.context import suppress_send_recording

    async with suppress_send_recording():
        if not segment_enabled:
            cleaned = strip_seg_tags(reply_text)
            if cleaned:
                await bot.send(event, cleaned)
            return

        segments = split_segments(reply_text)
        if not segments:
            return

        for i, segment in enumerate(segments):
            await bot.send(event, segment)
            if i < len(segments) - 1:
                await asyncio.sleep(segment_delay)


def extract_event_info(bot: Bot, event: Event) -> dict[str, Any]:
    from apeiria.bot.platform import build_session_id, resolve_session

    platform, scene_type, scene_id = resolve_session(bot, event)
    session_id = build_session_id(bot, event)

    try:
        user_id = event.get_user_id()
    except (AttributeError, ValueError):
        user_id = ""

    is_at_bot = _check_is_tome(event)
    is_private = scene_type == "private"

    try:
        plain_text = sanitize_input(event.get_plaintext().strip())
    except (AttributeError, ValueError):
        plain_text = ""

    return {
        "session_id": session_id,
        "user_id": user_id,
        "platform": platform,
        "scene_type": scene_type,
        "scene_id": scene_id,
        "is_at_bot": is_at_bot,
        "is_private": is_private,
        "plain_text": plain_text,
    }


def _check_is_tome(event: Event) -> bool:
    try:
        return event.is_tome()
    except (AttributeError, TypeError):
        return False
