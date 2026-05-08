from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException, WebSocketDisconnect

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.app.chat.connection import WebChatConnection
from apeiria.app.chat.gateway import ChatGatewayService
from apeiria.app.chat.protocol import (
    ChatEnvelope,
    ChatSessionState,
    MessageReceivePayload,
    PartialReplyDeltaPayload,
    PartialReplyStartPayload,
    SessionCreatePayload,
    SessionSelectPayload,
    SessionSnapshotPayload,
    SessionStatus,
    TextSegment,
    WebUIPrincipal,
)
from apeiria.app.chat.session import ChatSession
from apeiria.app.chat.state import WebChatStateManager
from apeiria.app.chat.store import WebChatStore
from apeiria.app.chat.transport import serve_chat_websocket

if TYPE_CHECKING:
    import pytest

HISTORY_LIMIT = 100


class _StoreStub(WebChatStore):
    def __init__(self) -> None:
        self.saved_payloads: list[
            tuple[
                dict[str, ChatSession],
                dict[str, list[MessageReceivePayload]],
            ]
        ] = []

    def load(
        self,
    ) -> tuple[dict[str, ChatSession], dict[str, list[MessageReceivePayload]]]:
        return {}, {}

    def save(
        self,
        sessions: dict[str, ChatSession],
        history: dict[str, list[MessageReceivePayload]],
    ) -> None:
        self.saved_payloads.append((dict(sessions), dict(history)))


class _ConnectionStub(WebChatConnection):
    def __init__(
        self,
        principal: WebUIPrincipal | None,
        *,
        active_session_id: str | None = None,
    ) -> None:
        self.principal = principal
        self.active_session_id = active_session_id
        self.sent_envelopes: list[tuple[str, object, str | None]] = []

    async def send_envelope(
        self,
        type_: str,
        payload: object,
        request_id: str | None = None,
    ) -> None:
        self.sent_envelopes.append((type_, payload, request_id))


class _WebSocketStub:
    def __init__(self, frames: list[object]) -> None:
        self.frames = frames
        self.accepted = False
        self.sent_json: list[object] = []
        self.closed: list[tuple[int, str | None]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> object:
        if not self.frames:
            raise WebSocketDisconnect
        return self.frames.pop(0)

    async def send_json(self, payload: object) -> None:
        self.sent_json.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed.append((code, reason))


def _principal() -> WebUIPrincipal:
    return WebUIPrincipal(id="admin-1", username="admin", role="admin")


def _auth_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="admin-1",
            display_name="admin",
            role=PrincipalRole(role_id="admin"),
        ),
        auth_method="bearer_token",
        session_version=1,
        token_subject="admin-1",
    )


def _token_verifier(token: str) -> AuthSession:
    del token
    return _auth_session()


def test_create_session_reuses_existing_session_for_same_principal_and_target() -> None:
    state = WebChatStateManager(store=_StoreStub())
    principal = _principal()

    first = state.create_session(
        principal,
        SessionCreatePayload(target_user_id="10001"),
    )
    second = state.create_session(
        principal,
        SessionCreatePayload(target_user_id="10001"),
    )

    assert second.session_id == first.session_id
    assert len(state.iter_sessions_for_principal(principal.id)) == 1


def test_append_history_trims_to_latest_100_messages() -> None:
    state = WebChatStateManager(store=_StoreStub())
    session = state.create_session(
        _principal(),
        SessionCreatePayload(target_user_id="10001"),
    )
    start = datetime(2026, 4, 26, tzinfo=timezone.utc)

    for index in range(105):
        state.append_history(
            MessageReceivePayload(
                session_id=session.session_id,
                message_id=f"msg-{index}",
                role="user",
                segments=[TextSegment(text=f"message {index}")],
                timestamp=start + timedelta(seconds=index),
            )
        )

    history = state.get_history(session.session_id)

    assert len(history) == HISTORY_LIMIT
    assert history[0].message_id == "msg-5"
    assert history[-1].message_id == "msg-104"


def test_partial_reply_frames_do_not_append_session_history() -> None:
    from apeiria.app.chat.assets import AssetManager
    from apeiria.app.chat.emitter import WebChatEmitter

    store = _StoreStub()
    state = WebChatStateManager(store=store)
    principal = _principal()
    session = state.create_session(
        principal,
        SessionCreatePayload(target_user_id="10001"),
    )
    connection = _ConnectionStub(
        principal=principal,
        active_session_id=session.session_id,
    )
    emitter = WebChatEmitter(state, AssetManager())

    asyncio.run(
        emitter.emit_partial_reply_start(
            connection,
            PartialReplyStartPayload(
                session_id=session.session_id,
                trace_id="trace-1",
                stream_id="stream-1",
            ),
        )
    )
    asyncio.run(
        emitter.emit_partial_reply_delta(
            connection,
            PartialReplyDeltaPayload(
                session_id=session.session_id,
                trace_id="trace-1",
                stream_id="stream-1",
                content_delta="hello",
            ),
        )
    )

    assert state.get_history(session.session_id) == []
    assert [frame[0] for frame in connection.sent_envelopes] == [
        "reply.partial.start",
        "reply.partial.delta",
    ]


def test_select_session_returns_exact_requested_session_when_targets_duplicate() -> (
    None
):
    state = WebChatStateManager(store=_StoreStub())
    principal = _principal()
    start = datetime(2026, 4, 26, tzinfo=timezone.utc)
    older = ChatSession(
        session_id="sess-older",
        created_by=principal,
        target_user_id="10001",
        status=SessionStatus.READY,
        created_at=start,
        updated_at=start,
    )
    newer = ChatSession(
        session_id="sess-newer",
        created_by=principal,
        target_user_id="10001",
        status=SessionStatus.READY,
        created_at=start + timedelta(seconds=1),
        updated_at=start + timedelta(seconds=1),
    )
    state._sessions = {
        older.session_id: older,
        newer.session_id: newer,
    }
    state._history = {
        older.session_id: [],
        newer.session_id: [],
    }

    selected = state.select_session(
        principal,
        SessionSelectPayload(
            session_id="sess-older",
        ),
    )

    assert selected.session_id == "sess-older"


def test_clear_history_emits_session_snapshot(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    service = ChatGatewayService()
    principal = _principal()
    session = ChatSessionState(
        session_id="sess-existing",
        status=SessionStatus.READY,
        target_user_id="10001",
        created_by=principal,
        created_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
    )
    observed: dict[str, object] = {}

    def clear_history(
        session_id: str,
        principal_arg: WebUIPrincipal,
    ) -> ChatSessionState:
        observed["cleared_session_id"] = session_id
        observed["cleared_principal_id"] = principal_arg.id
        return session

    snapshot = SessionSnapshotPayload(
        active_session=session,
        sessions=[],
        history=[],
    )

    def build_session_snapshot(
        _principal: WebUIPrincipal,
        _active_session_id: str | None,
    ) -> SessionSnapshotPayload:
        return snapshot

    monkeypatch.setattr(
        "apeiria.app.chat.gateway.web_chat_service.clear_history",
        clear_history,
    )
    monkeypatch.setattr(
        "apeiria.app.chat.gateway.web_chat_service.emitter.build_session_snapshot",
        build_session_snapshot,
    )

    connection = _ConnectionStub(principal=principal, active_session_id="sess-existing")

    result = asyncio.run(
        service.handle_frame(
            connection,
            ChatEnvelope(type="session.clear_history", request_id="req-clear"),
            token_verifier=_token_verifier,
        )
    )

    assert result is None
    assert observed["cleared_session_id"] == "sess-existing"
    assert observed["cleared_principal_id"] == principal.id
    assert connection.sent_envelopes[-1][0] == "session.snapshot"
    assert connection.sent_envelopes[-1][1] == snapshot
    assert connection.sent_envelopes[-1][2] == "req-clear"


def test_gateway_rejects_non_auth_frames_without_principal(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    service = ChatGatewayService()
    frame = ChatEnvelope(type="session.list")
    connection = _ConnectionStub(principal=None)
    observed: dict[str, object] = {}

    async def emit_error(
        _connection: object,
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        type_: str = "system.error",
    ) -> None:
        observed.update(
            code=code,
            message=message,
            request_id=request_id,
            type_=type_,
        )

    monkeypatch.setattr(
        "apeiria.app.chat.gateway.web_chat_service.emit_error",
        emit_error,
    )

    result = asyncio.run(
        service.handle_frame(
            connection,
            frame,
            token_verifier=_token_verifier,
        )
    )

    assert result is None
    assert observed["code"] == "AUTH_REQUIRED"
    assert observed["type_"] == "system.error"


def test_gateway_maps_http_auth_failures_to_auth_error(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    service = ChatGatewayService()
    frame = ChatEnvelope(
        type="auth.hello",
        request_id="req-auth",
        payload={"token": "expired-token"},
    )
    connection = _ConnectionStub(principal=None)
    observed: dict[str, object] = {}

    async def emit_error(
        _connection: object,
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        type_: str = "system.error",
    ) -> None:
        observed.update(
            code=code,
            message=message,
            request_id=request_id,
            type_=type_,
        )

    def token_verifier(token: str) -> AuthSession:
        del token
        raise HTTPException(status_code=401, detail="token expired")

    monkeypatch.setattr(
        "apeiria.app.chat.gateway.web_chat_service.emit_error",
        emit_error,
    )

    result = asyncio.run(
        service.handle_frame(
            connection,
            frame,
            token_verifier=token_verifier,
        )
    )

    assert result is None
    assert observed["code"] == "AUTH_FAILED"
    assert observed["message"] == "token expired"
    assert observed["request_id"] == "req-auth"
    assert observed["type_"] == "auth.error"


def test_auth_hello_emits_session_snapshot(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    service = ChatGatewayService()
    frame = ChatEnvelope(
        type="auth.hello",
        request_id="req-auth",
        payload={"token": "valid-token"},
    )
    connection = _ConnectionStub(principal=None)
    snapshot = SessionSnapshotPayload(
        active_session=None,
        sessions=[],
        history=[],
    )

    def build_session_snapshot(
        _principal: WebUIPrincipal,
        _active_session_id: str | None,
    ) -> SessionSnapshotPayload:
        return snapshot

    monkeypatch.setattr(
        "apeiria.app.chat.gateway.web_chat_service.emitter.build_session_snapshot",
        build_session_snapshot,
    )

    result = asyncio.run(
        service.handle_frame(
            connection,
            frame,
            token_verifier=_token_verifier,
        )
    )

    assert result is None
    assert connection.principal is not None
    assert connection.sent_envelopes[-1][0] == "session.snapshot"
    assert connection.sent_envelopes[-1][1] == snapshot
    assert connection.sent_envelopes[-1][2] == "req-auth"


def test_websocket_invalid_frame_emits_error_and_continues(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    websocket = _WebSocketStub(
        [
            {"version": "1.0", "payload": {}},
            {"version": "1.0", "type": "capabilities.request", "payload": {}},
        ]
    )
    handled_frames: list[str] = []

    async def handle_frame(
        _connection: WebChatConnection,
        frame: ChatEnvelope,
        _token_verifier: object,
    ) -> None:
        handled_frames.append(frame.type)

    monkeypatch.setattr(
        "apeiria.app.chat.transport.chat_gateway_service.handle_frame",
        handle_frame,
    )

    result = asyncio.run(serve_chat_websocket(websocket, _token_verifier))

    assert result is None
    assert websocket.accepted is True
    assert websocket.closed == []
    assert handled_frames == ["capabilities.request"]
    assert websocket.sent_json[0]["type"] == "system.error"
    assert websocket.sent_json[0]["payload"]["code"] == "INVALID_FRAME"
