"""Incoming message orchestration for WebChat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger
from nonebot.message import handle_event

from apeiria.i18n import t

from .adapter import WebChatAdapter
from .bot import WebChatBot
from .connection import WebChatConnectionClosed
from .event import WebChatMessageEvent
from .protocol import (
    ChatSegment,
    MessageAckPayload,
    MessageReceivePayload,
    MessageSendPayload,
)

if TYPE_CHECKING:
    from .codec import MessageCodec
    from .connection import WebChatConnection
    from .emitter import WebChatEmitter
    from .session import ChatSession
    from .state import WebChatStateManager


class WebChatMessageHandler:
    """Validate and dispatch inbound messages into NoneBot events.

    This keeps the façade thin by concentrating the inbound message flow:
    ack -> persist/display user message -> build bot/event -> dispatch event.
    """

    def __init__(
        self,
        state: WebChatStateManager,
        codec: MessageCodec,
        emitter: WebChatEmitter,
    ) -> None:
        self._state = state
        self._codec = codec
        self._emitter = emitter
        self._adapter: WebChatAdapter | None = None

    async def handle_message(
        self,
        connection: "WebChatConnection",
        payload: MessageSendPayload,
    ) -> None:
        """Process one client message frame for an already-authenticated session."""
        session = self._state.get_session(payload.session_id)
        if not connection.principal:
            from apeiria.app.chat.gateway import ChatSessionForbiddenError

            raise ChatSessionForbiddenError(t("web_ui.sessions.owner_mismatch"))
        self._state.ensure_owner(session, connection.principal)
        connection.active_session_id = session.session_id

        await connection.send_envelope(
            "message.ack",
            MessageAckPayload(
                session_id=session.session_id,
                message_id=payload.message_id,
                accepted=True,
            ),
        )

        await self._emitter.emit_message(
            connection,
            MessageReceivePayload(
                session_id=session.session_id,
                message_id=payload.message_id,
                role="user",
                segments=payload.segments,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        logger.info(
            "[webui-chat] principal={} session={} user={} msg={}",
            session.created_by.username,
            session.session_id,
            session.target_user_id,
            self._emitter.summarize_segments(payload.segments),
        )

        bot = WebChatBot(
            self._get_adapter(),
            session,
            connection,
            self._codec,
            self._emitter,
        )
        try:
            event = self._build_event(session, payload.message_id, payload.segments)
            await handle_event(bot, event)
        except WebChatConnectionClosed:
            logger.debug(
                "Web UI chat connection closed while handling session={}",
                session.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "Unhandled error in web chat message handling for session={}",
                session.session_id,
            )
            try:
                await bot.emit_error(t("web_ui.chat.internal_error"))
            except WebChatConnectionClosed:
                logger.debug(
                    "Web UI chat closed before error delivery for session={}",
                    session.session_id,
                )

    def _get_adapter(self) -> WebChatAdapter:
        if self._adapter is None:
            import nonebot

            self._adapter = WebChatAdapter(nonebot.get_driver())
        return self._adapter

    def _build_event(
        self,
        session: "ChatSession",
        message_id: str,
        segments: list[ChatSegment],
    ) -> WebChatMessageEvent:
        """Translate protocol segments into the NoneBot event consumed by handlers."""
        return WebChatMessageEvent(
            session=session,
            message=self._codec.decode_segments(segments),
            message_id=message_id,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
        )
