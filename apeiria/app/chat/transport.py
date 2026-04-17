"""WebSocket transport loop for Web UI chat."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from nonebot.log import logger
from pydantic import ValidationError

from apeiria.app.chat.service import chat_gateway_service
from apeiria.app.chat.web_chat import WebChatConnection, web_chat_service
from apeiria.shared.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.shared.principal import AuthSession


async def serve_chat_websocket(
    websocket: WebSocket,
    token_verifier: Callable[[str], "AuthSession"],
) -> None:
    """Run the full websocket session loop for one browser connection."""
    await websocket.accept()
    connection = WebChatConnection(websocket)
    active_session_id: str | None = None

    try:
        while True:
            frame = chat_gateway_service.parse_frame(await websocket.receive_json())
            active_session_id = await chat_gateway_service.handle_frame(
                connection,
                frame,
                active_session_id,
                token_verifier,
            )
    except ValidationError as exc:
        await web_chat_service.emit_error(
            connection,
            code="INVALID_FRAME",
            message=f"{t('web_ui.chat.invalid_frame')}: {exc}",
            type_="system.error",
        )
    except WebSocketDisconnect:
        if active_session_id:
            web_chat_service.close_session(active_session_id)
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).error("Web UI chat websocket loop crashed")
        await web_chat_service.emit_error(
            connection,
            code="INTERNAL_ERROR",
            message=f"{t('web_ui.chat.internal_error')}: {exc}",
            type_="system.error",
        )
        await websocket.close(
            code=1011,
            reason=t("web_ui.chat.websocket_close_reason"),
        )
