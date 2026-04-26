"""Message codec for WebChat."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote, urlparse

from .message import WebChatMessage, WebChatMessageSegment
from .protocol import (
    ChatSegment,
    ImageSegment,
    MentionSegment,
    RawSegment,
    ReplySegment,
    TextSegment,
)

if TYPE_CHECKING:
    from .assets import AssetManager


class MessageCodec:
    def __init__(self, asset_manager: "AssetManager") -> None:
        self._asset_manager = asset_manager

    def decode_segments(self, segments: list[ChatSegment]) -> WebChatMessage:
        built: list[WebChatMessageSegment] = []
        for segment in segments:
            if isinstance(segment, TextSegment):
                built.append(WebChatMessageSegment.text(segment.text))
            elif isinstance(segment, ImageSegment):
                built.append(
                    WebChatMessageSegment.image(
                        url=segment.url,
                        base64_data=segment.base64,
                        mime=segment.mime,
                        asset_id=segment.asset_id,
                        alt=segment.alt,
                    )
                )
            elif isinstance(segment, MentionSegment):
                built.append(
                    WebChatMessageSegment.mention(
                        segment.target,
                        display=segment.display,
                        mention_type=segment.mention_type,
                    )
                )
            elif isinstance(segment, ReplySegment):
                built.append(
                    WebChatMessageSegment.reply(
                        segment.message_id,
                        text=segment.text,
                    )
                )
            elif isinstance(segment, RawSegment):
                built.append(
                    WebChatMessageSegment(
                        type=segment.segment_type,
                        data=segment.data,
                    )
                )
        return WebChatMessage(built)

    async def encode_message(
        self,
        message: str | WebChatMessage | WebChatMessageSegment,
    ) -> list[ChatSegment]:
        if isinstance(message, str):
            return [TextSegment(text=message)]
        if isinstance(message, WebChatMessageSegment):
            return [await self._encode_segment(message)]

        encoded = [await self._encode_segment(segment) for segment in message]
        return encoded or [TextSegment(text=str(message))]

    async def _encode_segment(  # noqa: C901, PLR0911
        self,
        segment: WebChatMessageSegment,
    ) -> ChatSegment:
        if segment.is_text():
            return TextSegment(text=str(segment))

        if segment.type == "image":
            data = cast("dict[str, Any]", segment.data)
            url = data.get("url")
            if isinstance(url, str) and url:
                return ImageSegment(url=url, alt=data.get("alt"))

            base64_data = data.get("base64")
            if isinstance(base64_data, str) and base64_data:
                return ImageSegment(
                    base64=base64_data,
                    mime=str(data.get("mime") or "image/png"),
                    asset_id=cast("str | None", data.get("asset_id")),
                    alt=cast("str | None", data.get("alt")),
                )

            file_path = data.get("file") or data.get("path")
            if isinstance(file_path, str) and file_path:
                if file_path.startswith("base64://"):
                    return ImageSegment(
                        base64=file_path.removeprefix("base64://"),
                        mime=str(data.get("mime") or "image/png"),
                        alt=cast("str | None", data.get("alt")),
                    )

                resolved_path = self._resolve_local_file(file_path)
                if resolved_path and resolved_path.is_file():
                    asset = self._asset_manager.register_path(
                        resolved_path,
                        content_type=mimetypes.guess_type(resolved_path.name)[0]
                        or "image/png",
                        file_name=resolved_path.name,
                    )
                    mime, _ = mimetypes.guess_type(resolved_path.name)
                    return ImageSegment(
                        url=f"/api/chat/assets/{asset.asset_id}",
                        asset_id=asset.asset_id,
                        mime=mime or "image/png",
                        alt=cast("str | None", data.get("alt")),
                    )

            raw = data.get("raw") or data.get("bytes")
            if isinstance(raw, bytes):
                return ImageSegment(
                    base64=base64.b64encode(raw).decode("ascii"),
                    mime=str(data.get("mime") or "image/png"),
                    alt=cast("str | None", data.get("alt")),
                )

            return RawSegment(segment_type="image", data=dict(data))

        if segment.type == "mention":
            data = cast("dict[str, Any]", segment.data)
            target = data.get("target")
            if isinstance(target, str) and target:
                return MentionSegment(
                    target=target,
                    display=cast("str | None", data.get("display")),
                    mention_type=str(data.get("mention_type") or "user"),
                )
            return RawSegment(segment_type="mention", data=dict(data))

        if segment.type == "reply":
            data = cast("dict[str, Any]", segment.data)
            message_id = data.get("message_id") or data.get("id")
            if isinstance(message_id, str) and message_id:
                return ReplySegment(
                    message_id=message_id,
                    text=cast("str | None", data.get("text")),
                )
            return RawSegment(segment_type="reply", data=dict(data))

        return RawSegment(segment_type=segment.type, data=dict(segment.data))

    def _resolve_local_file(self, value: str) -> Path | None:
        if value.startswith("file://"):
            parsed = urlparse(value)
            return Path(unquote(parsed.path))
        if "://" in value:
            return None
        return Path(value)
