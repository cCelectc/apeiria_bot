from __future__ import annotations

from collections.abc import Iterable
from typing import Any, override

from nonebot.adapters import Message as BaseMessage
from nonebot.adapters import MessageSegment as BaseMessageSegment


class MessageSegment(BaseMessageSegment["Message"]):
    """WebChat 消息段：text / image / raw。"""

    @classmethod
    @override
    def get_message_class(cls) -> type[Message]:
        return Message

    @override
    def __str__(self) -> str:
        if self.type == "text":
            return self.data.get("text", "")
        if self.type == "image":
            return "[image]"
        if self.type == "raw":
            return f"[{self.data.get('seg_type', 'raw')}]"
        return f"[{self.type}]"

    @override
    def is_text(self) -> bool:
        return self.type == "text"

    @classmethod
    def text(cls, text: str) -> MessageSegment:
        return cls("text", {"text": text})

    @classmethod
    def image(
        cls, *, url: str | None = None, base64: str | None = None
    ) -> MessageSegment:
        return cls("image", {"url": url, "base64": base64})

    @classmethod
    def raw(cls, seg_type: str, data: dict[str, Any]) -> MessageSegment:
        """出站调试兜底：保真承载未知/不支持的消息段。"""
        return cls("raw", {"seg_type": seg_type, "data": data})


class Message(BaseMessage[MessageSegment]):
    """WebChat 消息序列。"""

    @classmethod
    @override
    def get_segment_class(cls) -> type[MessageSegment]:
        return MessageSegment

    @staticmethod
    @override
    def _construct(msg: str) -> Iterable[MessageSegment]:
        if msg:
            yield MessageSegment.text(msg)
