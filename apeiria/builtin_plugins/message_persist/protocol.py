from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


@dataclass
class ExtractedMessage:
    content: str
    plain_text: str
    user_id: str
    message_id: str | None = None
    meta: dict[str, Any] | None = None
    is_bot_message: bool = False


@runtime_checkable
class MessageExtractor(Protocol):
    def supports(self, bot: Bot, event: Event) -> bool: ...
    def extract(self, bot: Bot, event: Event) -> ExtractedMessage | None: ...
