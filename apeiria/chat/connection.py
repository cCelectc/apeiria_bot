"""Connection wrapper for WebChat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .protocol import ChatEnvelope, WebUIPrincipal

if TYPE_CHECKING:
    from fastapi import WebSocket


class WebChatConnection:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.principal: WebUIPrincipal | None = None

    async def send_envelope(
        self,
        type_: str,
        payload: Any,
        request_id: str | None = None,
    ) -> None:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        envelope = ChatEnvelope(type=type_, request_id=request_id, payload=payload)
        await self.websocket.send_json(envelope.model_dump(mode="json"))
