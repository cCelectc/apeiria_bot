"""Bot implementation for WebChat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from nonebot.adapters import Bot, Event, Message, MessageSegment
from nonebot.log import logger

from .message import WebChatMessage, WebChatMessageSegment
from .protocol import ErrorPayload, MessageReceivePayload

if TYPE_CHECKING:
    from .codec import MessageCodec
    from .connection import WebChatConnection
    from .emitter import WebChatEmitter
    from .session import ChatSession


class WebChatBot(Bot):
    _session: "ChatSession"
    _connection: "WebChatConnection"
    _codec: "MessageCodec"
    _emitter: "WebChatEmitter"

    def __init__(
        self,
        adapter: Any,
        session: "ChatSession",
        connection: "WebChatConnection",
        codec: "MessageCodec",
        emitter: "WebChatEmitter",
    ) -> None:
        super().__init__(adapter, f"webui_{session.session_id}")
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_codec", codec)
        object.__setattr__(self, "_emitter", emitter)

    async def send(
        self,
        event: Event,  # noqa: ARG002
        message: str | Message | MessageSegment,
        **kwargs: Any,  # noqa: ARG002
    ) -> Any:
        if isinstance(message, (str, WebChatMessage, WebChatMessageSegment)):
            encoded_message = message
        else:
            encoded_message = str(message)

        segments = await self._codec.encode_message(encoded_message)
        payload = MessageReceivePayload(
            session_id=self._session.session_id,
            message_id=f"srv_{uuid4().hex}",
            role="bot",
            segments=segments,
            timestamp=datetime.now(timezone.utc),
        )
        await self._emitter.emit_message(self._connection, payload)
        return {"status": "ok"}

    async def call_api(self, api: str, **data: Any) -> Any:
        logger.debug("Unhandled WebUI chat API call: {} {}", api, data)
        return None

    async def emit_error(self, message: str) -> None:
        await self._connection.send_envelope(
            "message.error",
            ErrorPayload(code="HANDLE_EVENT_ERROR", message=message),
        )
