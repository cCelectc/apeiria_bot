"""Protocol emitter for WebChat responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .protocol import (
    AuthOkPayload,
    CapabilitiesResponsePayload,
    ChatCapabilities,
    ErrorPayload,
    ImageSegment,
    MentionSegment,
    MessageReceivePayload,
    ReplySegment,
    SessionDeletedPayload,
    SessionListItem,
    SessionListPayload,
    SessionStatePayload,
    SystemMessagePayload,
    TextSegment,
    WebUIPrincipal,
)

if TYPE_CHECKING:
    from .assets import AssetManager
    from .connection import WebChatConnection
    from .session import ChatSession
    from .state import WebChatStateManager


class WebChatEmitter:
    """Build protocol payloads and send them through websocket connections.

    This object owns outbound protocol concerns only:
    - shaping response payloads
    - ordering session list output
    - appending persisted message history before emitting frames
    """

    def __init__(
        self,
        state: WebChatStateManager,
        assets: AssetManager,
    ) -> None:
        self._state = state
        self._assets = assets

    def get_capabilities(self) -> ChatCapabilities:
        return ChatCapabilities(
            segment_types=["text", "image", "mention", "reply", "raw"],
            mock_apis=[],
        )

    def list_sessions(self, principal: WebUIPrincipal) -> list[SessionListItem]:
        """Return sessions sorted the same way the Web UI expects to render them."""
        sessions = [
            self._build_session_list_item(session)
            for session in self._state.iter_sessions_for_principal(principal.id)
        ]
        return sorted(
            sessions,
            key=lambda item: (
                item.last_message_at
                or item.session.updated_at
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )

    async def emit_auth_ok(
        self,
        connection: "WebChatConnection",
        principal: WebUIPrincipal,
        request_id: str | None = None,
    ) -> None:
        connection.principal = principal
        await connection.send_envelope(
            "auth.ok",
            AuthOkPayload(principal=principal),
            request_id=request_id,
        )

    async def emit_capabilities(
        self,
        connection: "WebChatConnection",
        request_id: str | None = None,
    ) -> None:
        await connection.send_envelope(
            "capabilities.response",
            CapabilitiesResponsePayload(capabilities=self.get_capabilities()),
            request_id=request_id,
        )

    async def emit_session_state(
        self,
        connection: "WebChatConnection",
        session: Any,
        request_id: str | None = None,
        *,
        type_: str = "session.state",
    ) -> None:
        await connection.send_envelope(
            type_,
            SessionStatePayload(
                session=session,
                history=self._state.get_history(session.session_id),
            ),
            request_id=request_id,
        )

    async def emit_session_list(
        self,
        connection: "WebChatConnection",
        principal: WebUIPrincipal,
        request_id: str | None = None,
    ) -> None:
        await connection.send_envelope(
            "session.list",
            SessionListPayload(sessions=self.list_sessions(principal)),
            request_id=request_id,
        )

    async def emit_system_info(
        self,
        connection: "WebChatConnection",
        message: str,
    ) -> None:
        await connection.send_envelope(
            "system.info",
            SystemMessagePayload(message=message),
        )

    async def emit_message(
        self,
        connection: "WebChatConnection",
        payload: MessageReceivePayload,
    ) -> None:
        """Persist one outbound/inbound message and emit it to the client."""
        self._state.append_history(payload)
        self.prune_assets()
        await connection.send_envelope("message.receive", payload)

    async def emit_error(
        self,
        connection: "WebChatConnection",
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        type_: str = "system.error",
    ) -> None:
        await connection.send_envelope(
            type_,
            ErrorPayload(code=code, message=message),
            request_id=request_id,
        )

    async def emit_session_deleted(
        self,
        connection: "WebChatConnection",
        session_id: str,
        request_id: str | None = None,
    ) -> None:
        await connection.send_envelope(
            "session.deleted",
            SessionDeletedPayload(session_id=session_id),
            request_id=request_id,
        )

    def summarize_segments(self, segments: list[Any]) -> str:
        """Build a compact plain-text summary for logs and session previews."""
        parts: list[str] = []
        for segment in segments:
            if isinstance(segment, TextSegment):
                parts.append(segment.text)
            elif isinstance(segment, ImageSegment):
                parts.append("[image]")
            elif isinstance(segment, MentionSegment):
                parts.append(f"@{segment.display or segment.target}")
            elif isinstance(segment, ReplySegment):
                parts.append(f"[reply:{segment.message_id}]")
            else:
                parts.append(f"[{segment.segment_type}]")
        return " ".join(parts)

    def prune_assets(self) -> None:
        self._assets.retain(self._state.referenced_asset_ids())

    def _build_session_list_item(self, session: "ChatSession") -> SessionListItem:
        history = self._state.get_history(session.session_id)
        last_message = history[-1] if history else None
        return SessionListItem(
            session=session.to_state(),
            message_count=len(history),
            last_message=(
                self.summarize_segments(last_message.segments) if last_message else None
            ),
            last_message_at=last_message.timestamp if last_message else None,
        )
