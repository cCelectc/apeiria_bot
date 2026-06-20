from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.builtin_plugins.message_persist.protocol import (
        ExtractedMessage,
        MessageExtractor,
    )

_extractors: list[MessageExtractor] = []


def register_extractor(ext: MessageExtractor) -> None:
    _extractors.append(ext)


def extract_message(bot: Bot, event: Event) -> ExtractedMessage | None:
    for ext in _extractors:
        if ext.supports(bot, event):
            return ext.extract(bot, event)
    return None
