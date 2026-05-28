"""Connection wrapper for WebChat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.websockets import WebSocketDisconnect, WebSocketState

from .protocol import ChatEnvelope, WebUIPrincipal

if TYPE_CHECKING:
    from fastapi import WebSocket


class WebChatConnectionClosed(WebSocketDisconnect):
    """Raised when a WebChat websocket is already closed or becomes closed."""


class WebChatConnection:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.principal: WebUIPrincipal | None = None
        self.active_session_id: str | None = None

    async def send_envelope(
        self,
        type_: str,
        payload: Any,
        request_id: str | None = None,
    ) -> None:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        envelope = ChatEnvelope(type=type_, request_id=request_id, payload=payload)
        if self._is_disconnected():
            raise WebChatConnectionClosed(code=1006)
        try:
            await self.websocket.send_json(envelope.model_dump(mode="json"))
        except WebSocketDisconnect as exc:
            raise WebChatConnectionClosed(code=exc.code, reason=exc.reason) from exc
        except RuntimeError as exc:
            if self._is_closed_runtime_error(exc):
                raise WebChatConnectionClosed(code=1006) from exc
            raise

    @staticmethod
    def _is_closed_runtime_error(exc: RuntimeError) -> bool:
        return str(exc) in {
            'Cannot call "send" once a close message has been sent.',
            'WebSocket is not connected. Need to call "accept" first.',
            'Cannot call "receive" once a disconnect message has been received.',
        }

    def _is_disconnected(self) -> bool:
        disconnected = WebSocketState.DISCONNECTED
        return self.websocket.client_state is disconnected or (
            self.websocket.application_state is disconnected
        )
