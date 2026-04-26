"""Message types for WebChat."""

from __future__ import annotations

from typing import Any

from nonebot.adapters import Message, MessageSegment


class WebChatMessage(Message["WebChatMessageSegment"]):
    @classmethod
    def get_segment_class(cls) -> type["WebChatMessageSegment"]:
        return WebChatMessageSegment

    @staticmethod
    def _construct(msg: str) -> list["WebChatMessageSegment"]:
        return [WebChatMessageSegment.text(msg)]


class WebChatMessageSegment(MessageSegment):
    @classmethod
    def get_message_class(cls) -> type[WebChatMessage]:
        return WebChatMessage

    def __str__(self) -> str:
        if self.type == "text":
            return str(self.data.get("text", ""))
        if self.type == "image":
            return "[image]"
        if self.type == "mention":
            return f"@{self.data.get('display') or self.data.get('target') or 'user'}"
        if self.type == "reply":
            reply_id = self.data.get("message_id") or self.data.get("id") or "message"
            return f"[reply:{reply_id}]"
        return f"[{self.type}]"

    def is_text(self) -> bool:
        return self.type == "text"

    @classmethod
    def text(cls, text: str) -> "WebChatMessageSegment":
        return cls(type="text", data={"text": text})

    @classmethod
    def image(
        cls,
        *,
        url: str | None = None,
        base64_data: str | None = None,
        mime: str | None = None,
        asset_id: str | None = None,
        alt: str | None = None,
    ) -> "WebChatMessageSegment":
        data: dict[str, Any] = {}
        if url:
            data["url"] = url
        if base64_data:
            data["base64"] = base64_data
        if mime:
            data["mime"] = mime
        if asset_id:
            data["asset_id"] = asset_id
        if alt:
            data["alt"] = alt
        return cls(type="image", data=data)

    @classmethod
    def mention(
        cls,
        target: str,
        *,
        display: str | None = None,
        mention_type: str = "user",
    ) -> "WebChatMessageSegment":
        data: dict[str, Any] = {
            "target": target,
            "mention_type": mention_type,
        }
        if display:
            data["display"] = display
        return cls(type="mention", data=data)

    @classmethod
    def reply(
        cls,
        message_id: str,
        *,
        text: str | None = None,
    ) -> "WebChatMessageSegment":
        data: dict[str, Any] = {"message_id": message_id}
        if text:
            data["text"] = text
        return cls(type="reply", data=data)
