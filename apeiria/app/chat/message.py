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
            rendered = str(self.data.get("text", ""))
        elif self.type == "image":
            rendered = "[image]"
        elif self.type in {"record", "audio"}:
            rendered = "[audio]"
        elif self.type == "file":
            file_name = self.data.get("name") or self.data.get("file") or "file"
            rendered = f"[file:{file_name}]"
        elif self.type == "mention":
            mention_name = self.data.get("display") or self.data.get("target") or "user"
            rendered = f"@{mention_name}"
        elif self.type == "reply":
            reply_id = self.data.get("message_id") or self.data.get("id") or "message"
            rendered = f"[reply:{reply_id}]"
        else:
            rendered = f"[{self.type}]"
        return rendered

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
    def audio(  # noqa: PLR0913
        cls,
        *,
        url: str | None = None,
        base64_data: str | None = None,
        mime: str | None = None,
        asset_id: str | None = None,
        file: str | None = None,
        path: str | None = None,
        name: str | None = None,
        size: int | None = None,
        duration: float | None = None,
    ) -> "WebChatMessageSegment":
        data = _media_segment_data(
            {
                "url": url,
                "base64": base64_data,
                "mime": mime,
                "asset_id": asset_id,
                "file": file,
                "path": path,
                "name": name,
                "size": size,
            }
        )
        if duration is not None:
            data["duration"] = duration
        return cls(type="record", data=data)

    @classmethod
    def file(  # noqa: PLR0913
        cls,
        *,
        url: str | None = None,
        base64_data: str | None = None,
        mime: str | None = None,
        asset_id: str | None = None,
        file: str | None = None,
        path: str | None = None,
        name: str | None = None,
        size: int | None = None,
    ) -> "WebChatMessageSegment":
        data = _media_segment_data(
            {
                "url": url,
                "base64": base64_data,
                "mime": mime,
                "asset_id": asset_id,
                "file": file,
                "path": path,
                "name": name,
                "size": size,
            }
        )
        return cls(type="file", data=data)

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


def _media_segment_data(values: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        data[key] = value
    return data
