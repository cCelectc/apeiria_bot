from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.chat.gateway import ChatGatewayService
from apeiria.chat.protocol import (
    ChatEnvelope,
    MessageReceivePayload,
    SessionCreatePayload,
    TextSegment,
    WebUIPrincipal,
)
from apeiria.chat.state import WebChatStateManager

if TYPE_CHECKING:
    import pytest

HISTORY_LIMIT = 100


class _StoreStub:
    def __init__(self) -> None:
        self.saved_payloads: list[tuple[dict[str, object], dict[str, object]]] = []

    def load(self) -> tuple[dict[str, object], dict[str, object]]:
        return {}, {}

    def save(self, sessions: dict[str, object], history: dict[str, object]) -> None:
        self.saved_payloads.append((dict(sessions), dict(history)))


def _principal() -> WebUIPrincipal:
    return WebUIPrincipal(id="admin-1", username="admin", role="admin")


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


def test_gateway_rejects_non_auth_frames_without_principal(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    service = ChatGatewayService()
    frame = ChatEnvelope(type="session.list")
    connection = SimpleNamespace(principal=None)
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

    monkeypatch.setattr("apeiria.chat.gateway.web_chat_service.emit_error", emit_error)

    result = asyncio.run(
        service.handle_frame(
            connection,
            frame,
            active_session_id="sess-existing",
            token_verifier=lambda token: token,
        )
    )

    assert result == "sess-existing"
    assert observed["code"] == "AUTH_REQUIRED"
    assert observed["type_"] == "system.error"
