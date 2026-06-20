from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketDisconnect, WebSocketState

from apeiria.webchat.bot import WebChatBot
from apeiria.webchat.connection import WebChatConnection, WebChatConnectionClosed
from apeiria.webchat.protocol import WebUIPrincipal
from apeiria.webchat.session import ChatSession
from apeiria.webchat.transport import serve_chat_websocket


class _FakeWebSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.application_state = WebSocketState.CONNECTED
        self.sent_payloads: list[object] = []
        self.close_calls: list[tuple[int, str]] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True
        self.application_state = WebSocketState.CONNECTED

    async def send_json(self, payload: object) -> None:
        self.sent_payloads.append(payload)

    async def receive_json(self) -> object:
        msg = 'Cannot call "receive" once a disconnect message has been received.'
        raise RuntimeError(msg)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.application_state = WebSocketState.DISCONNECTED
        self.close_calls.append((code, reason or ""))


class _FakeClosedSendWebSocket(_FakeWebSocket):
    async def send_json(self, _payload: object) -> None:
        raise WebSocketDisconnect(code=1006)


def test_send_envelope_raises_closed_for_disconnected_websocket() -> None:
    websocket = _FakeWebSocket()
    websocket.application_state = WebSocketState.DISCONNECTED
    connection = WebChatConnection(websocket)

    async def scenario() -> None:
        with pytest.raises(WebChatConnectionClosed):
            await connection.send_envelope("system.info", {"message": "x"})

    asyncio.run(scenario())


def test_send_envelope_wraps_websocket_disconnect() -> None:
    connection = WebChatConnection(_FakeClosedSendWebSocket())

    async def scenario() -> None:
        with pytest.raises(WebChatConnectionClosed):
            await connection.send_envelope("system.info", {"message": "x"})

    asyncio.run(scenario())


def test_serve_chat_websocket_closes_session_on_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = _FakeWebSocket()
    closed_sessions: list[str] = []

    async def fake_authenticate_session(
        connection: WebChatConnection,
        _session: object,
    ) -> None:
        connection.principal = WebUIPrincipal(
            id="admin",
            username="admin",
            role="webui_local_account",
        )
        connection.active_session_id = "sess_case"

    async def scenario() -> None:
        monkeypatch.setattr(
            "apeiria.webchat.transport.chat_gateway_service.authenticate_session",
            fake_authenticate_session,
        )
        monkeypatch.setattr(
            "apeiria.webchat.transport.web_chat_service.close_session",
            closed_sessions.append,
        )
        await serve_chat_websocket(websocket, session=object())

    asyncio.run(scenario())

    assert websocket.accepted is True
    assert closed_sessions == ["sess_case"]
    assert websocket.close_calls == []


def test_webchat_bot_send_returns_disconnected_on_closed_connection() -> None:
    class _Adapter:
        @staticmethod
        def get_name() -> str:
            return "webchat"

    class _Codec:
        @staticmethod
        async def encode_message(message: object) -> list[object]:
            return [{"type": "text", "text": str(message)}]

    class _Emitter:
        @staticmethod
        async def emit_message(_connection: object, _payload: object) -> None:
            raise WebChatConnectionClosed(code=1006)

    session = ChatSession.create(
        session_id="sess_case",
        created_by=WebUIPrincipal(
            id="admin",
            username="admin",
            role="webui_local_account",
        ),
        target_user_id="1779972307790",
    )
    bot = WebChatBot(
        _Adapter(),
        session,
        connection=object(),
        codec=_Codec(),
        emitter=_Emitter(),
    )

    async def scenario() -> None:
        result = await bot.send(SimpleNamespace(), "hello")
        assert result == {"status": "disconnected"}

    asyncio.run(scenario())
