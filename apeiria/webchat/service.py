"""Facade service for WebChat composition."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .assets import AssetManager, ChatAsset
from .codec import MessageCodec
from .emitter import WebChatEmitter
from .message_handler import WebChatMessageHandler
from .protocol import (
    ChatSessionState,
    MessageReceivePayload,
    MessageSendPayload,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionListItem,
    SessionSelectPayload,
    SessionSnapshotPayload,
    WebUIPrincipal,
)
from .state import WebChatStateManager

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession

    from .connection import WebChatConnection


class WebChatService:
    """Facade that composes the WebChat kernel pieces.

    This class intentionally stays thin. Stateful behavior lives in
    `WebChatStateManager`, outbound protocol formatting in `WebChatEmitter`,
    and inbound message orchestration in `WebChatMessageHandler`.
    """

    def __init__(self) -> None:
        self.state = WebChatStateManager()
        self.assets = AssetManager()
        self.codec = MessageCodec(self.assets)
        self.emitter = WebChatEmitter(self.state, self.assets)
        self.message_handler = WebChatMessageHandler(
            self.state,
            self.codec,
            self.emitter,
        )

    def build_principal(self, session: "AuthSession") -> WebUIPrincipal:
        """Normalize one auth session into the principal used by WebChat."""
        username = session.username or "webui"
        return WebUIPrincipal(
            id=session.user_id or "webui_admin",
            username=username,
            role="webui_local_account",
        )

    def create_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionCreatePayload,
    ) -> ChatSessionState:
        return self.state.create_session(principal, payload)

    def select_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionSelectPayload,
    ) -> ChatSessionState:
        return self.state.select_session(principal, payload)

    def get_asset(self, asset_id: str) -> ChatAsset | None:
        return self.assets.get(asset_id)

    def list_sessions(self, principal: WebUIPrincipal) -> list[SessionListItem]:
        return self.emitter.list_sessions(principal)

    async def handle_message(
        self,
        connection: "WebChatConnection",
        payload: MessageSendPayload,
    ) -> None:
        await self.message_handler.handle_message(connection, payload)

    async def emit_auth_ok(
        self,
        connection: "WebChatConnection",
        principal: WebUIPrincipal,
        request_id: str | None = None,
    ) -> None:
        await self.emitter.emit_auth_ok(connection, principal, request_id)

    async def emit_capabilities(
        self,
        connection: "WebChatConnection",
        request_id: str | None = None,
    ) -> None:
        await self.emitter.emit_capabilities(connection, request_id)

    def build_session_snapshot(
        self,
        principal: WebUIPrincipal,
        active_session_id: str | None,
    ) -> SessionSnapshotPayload:
        return self.emitter.build_session_snapshot(principal, active_session_id)

    async def emit_session_snapshot(
        self,
        connection: "WebChatConnection",
        request_id: str | None = None,
    ) -> None:
        await self.emitter.emit_session_snapshot(
            connection,
            request_id=request_id,
        )

    async def emit_system_info(
        self,
        connection: "WebChatConnection",
        message: str,
    ) -> None:
        await self.emitter.emit_system_info(connection, message)

    async def emit_message(
        self,
        connection: "WebChatConnection",
        payload: MessageReceivePayload,
    ) -> None:
        await self.emitter.emit_message(connection, payload)

    async def emit_error(
        self,
        connection: "WebChatConnection",
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        type_: str = "system.error",
    ) -> None:
        await self.emitter.emit_error(
            connection,
            code=code,
            message=message,
            request_id=request_id,
            type_=type_,
        )

    def close_session(self, session_id: str) -> None:
        self.state.close_session(session_id)

    def clear_history(
        self,
        session_id: str,
        principal: WebUIPrincipal,
    ) -> ChatSessionState:
        session = self.state.clear_history(session_id, principal)
        self.emitter.prune_assets()
        return session

    def delete_session(
        self,
        principal: WebUIPrincipal,
        payload: SessionDeletePayload,
    ) -> str:
        session_id = self.state.delete_session(principal, payload)
        self.emitter.prune_assets()
        return session_id


web_chat_service = WebChatService()
