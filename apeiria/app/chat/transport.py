"""WebSocket transport loop for Web UI chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from nonebot.log import logger
from pydantic import ValidationError

from apeiria.app.chat.connection import WebChatConnection, WebChatConnectionClosed
from apeiria.app.chat.gateway import chat_gateway_service
from apeiria.app.chat.service import web_chat_service
from apeiria.i18n import t

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


async def serve_chat_websocket(
    websocket: WebSocket,
    session: "AuthSession",
) -> None:
    """Run the full websocket session loop for one browser connection."""
    connection = WebChatConnection(websocket)
    accepted = False

    try:
        await websocket.accept()
        accepted = True
        await chat_gateway_service.authenticate_session(connection, session)
        while True:
            frame = await _receive_frame(websocket, connection)
            if frame is None:
                continue
            await chat_gateway_service.handle_frame(
                connection,
                frame,
            )
    except (WebSocketDisconnect, WebChatConnectionClosed):
        pass
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("Web UI chat websocket loop crashed")
        await _emit_internal_error(websocket, connection, accepted=accepted)
    finally:
        if connection.active_session_id:
            web_chat_service.close_session(connection.active_session_id)


async def _receive_frame(
    websocket: WebSocket,
    connection: WebChatConnection,
) -> object | None:
    try:
        return chat_gateway_service.parse_frame(await websocket.receive_json())
    except WebSocketDisconnect:
        raise
    except RuntimeError as exc:
        if _is_closed_receive_error(websocket, exc):
            raise WebChatConnectionClosed(code=1006) from exc
        raise
    except ValidationError as exc:
        logger.debug("Invalid websocket frame: {}", exc)
        await web_chat_service.emit_error(
            connection,
            code="INVALID_FRAME",
            message=t("web_ui.chat.invalid_frame"),
            type_="system.error",
        )
        return None


async def _emit_internal_error(
    websocket: WebSocket,
    connection: WebChatConnection,
    *,
    accepted: bool,
) -> None:
    try:
        await web_chat_service.emit_error(
            connection,
            code="INTERNAL_ERROR",
            message=t("web_ui.chat.internal_error"),
            type_="system.error",
        )
    except WebChatConnectionClosed:
        return
    if not accepted:
        return
    try:
        await websocket.close(
            code=1011,
            reason=t("web_ui.chat.websocket_close_reason"),
        )
    except WebSocketDisconnect:
        pass
    except RuntimeError as close_exc:
        if not _is_closed_receive_error(websocket, close_exc):
            raise


def _is_closed_receive_error(websocket: WebSocket, exc: RuntimeError) -> bool:
    return (
        websocket.client_state.name == "DISCONNECTED"
        or websocket.application_state.name == "DISCONNECTED"
        or str(exc)
        in {
            'WebSocket is not connected. Need to call "accept" first.',
            'Cannot call "receive" once a disconnect message has been received.',
            'Cannot call "send" once a close message has been sent.',
        }
    )
