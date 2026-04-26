"""Application service for Web UI chat gateway flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from apeiria.app.chat.gateway_protocol import (
    AuthHelloPayload,
    ChatEnvelope,
    MessageSendPayload,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionSelectPayload,
)
from apeiria.app.chat.service import web_chat_service
from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.access.principal import AuthSession
    from apeiria.app.chat.assets import ChatAsset
    from apeiria.app.chat.connection import WebChatConnection
    from apeiria.app.chat.protocol import WebUIPrincipal


class ChatAssetNotFoundError(ValueError):
    """Raised when a requested chat asset is unknown."""


class ChatAssetFileMissingError(ValueError):
    """Raised when a chat asset record exists but its file is missing."""


class ChatAuthError(ValueError):
    """Raised when a chat auth flow fails."""


class ChatGatewayService:
    """Adapt Web UI websocket frames onto the WebChat kernel."""

    def get_asset(self, asset_id: str) -> "ChatAsset":
        asset = web_chat_service.get_asset(asset_id)
        if asset is None:
            raise ChatAssetNotFoundError(asset_id)
        if asset.remote_url:
            return asset
        if asset.local_path and asset.local_path.is_file():
            return asset
        raise ChatAssetFileMissingError(asset_id)

    def parse_frame(self, payload: object) -> ChatEnvelope:
        return ChatEnvelope.model_validate(payload)

    async def handle_frame(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        token_verifier: Callable[[str], "AuthSession"],
    ) -> None:
        if frame.type != "auth.hello" and connection.principal is None:
            await web_chat_service.emit_error(
                connection,
                code="AUTH_REQUIRED",
                message=t("web_ui.chat.auth_required"),
                request_id=frame.request_id,
            )
            return

        if frame.type == "auth.hello":
            await self._handle_auth_hello(
                connection,
                frame,
                token_verifier,
            )
            return
        if frame.type == "capabilities.request":
            await web_chat_service.emit_capabilities(
                connection,
                request_id=frame.request_id,
            )
            return
        if frame.type in {
            "session.create",
            "session.select",
            "session.list",
            "session.close",
            "session.clear_history",
            "session.delete",
        }:
            await self._handle_session_frame(
                connection,
                frame,
            )
            return
        if frame.type == "message.send":
            await self._handle_message_send(
                connection,
                frame,
            )
            return
        await web_chat_service.emit_error(
            connection,
            code="UNSUPPORTED_FRAME",
            message=t("web_ui.chat.unsupported_frame", type=frame.type),
            request_id=frame.request_id,
        )

    async def _handle_session_frame(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
    ) -> None:
        match frame.type:
            case "session.create":
                await self._handle_session_create(
                    connection,
                    frame,
                )
            case "session.select":
                await self._handle_session_select(
                    connection,
                    frame,
                )
            case "session.list":
                await web_chat_service.emit_session_snapshot(
                    connection,
                    request_id=frame.request_id,
                )
            case "session.close":
                await self._handle_session_close(
                    connection,
                    frame.request_id,
                )
            case "session.clear_history":
                await self._handle_session_clear_history(
                    connection,
                    frame.request_id,
                )
            case "session.delete":
                await self._handle_session_delete(
                    connection,
                    frame,
                )

    async def _handle_session_create(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
    ) -> None:
        payload = SessionCreatePayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        session = web_chat_service.create_session(principal, payload)
        connection.active_session_id = session.session_id
        await web_chat_service.emit_session_snapshot(
            connection,
            request_id=frame.request_id,
        )

    async def _handle_session_select(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
    ) -> None:
        payload = SessionSelectPayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        session = web_chat_service.select_session(principal, payload)
        connection.active_session_id = session.session_id
        await web_chat_service.emit_session_snapshot(
            connection,
            request_id=frame.request_id,
        )

    async def _handle_message_send(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
    ) -> None:
        payload = MessageSendPayload.model_validate(frame.payload)
        await web_chat_service.handle_message(connection, payload)

    async def _handle_auth_hello(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        token_verifier: Callable[[str], "AuthSession"],
    ) -> None:
        try:
            payload = AuthHelloPayload.model_validate(frame.payload)
            session = token_verifier(payload.token)
            principal = web_chat_service.build_principal(session)
            connection.active_session_id = None
            await web_chat_service.emit_auth_ok(
                connection,
                principal,
                request_id=frame.request_id,
            )
            await web_chat_service.emit_system_info(
                connection,
                t("web_ui.chat.auth_connected"),
            )
            await web_chat_service.emit_session_snapshot(
                connection,
                request_id=frame.request_id,
            )
        except ChatAuthError as exc:
            await web_chat_service.emit_error(
                connection,
                code="AUTH_FAILED",
                message=str(exc),
                request_id=frame.request_id,
                type_="auth.error",
            )
        except HTTPException as exc:
            await web_chat_service.emit_error(
                connection,
                code="AUTH_FAILED",
                message=str(exc.detail),
                request_id=frame.request_id,
                type_="auth.error",
            )

    async def _handle_session_close(
        self,
        connection: WebChatConnection,
        request_id: str | None,
    ) -> None:
        if connection.active_session_id is not None:
            web_chat_service.close_session(connection.active_session_id)
        connection.active_session_id = None
        await web_chat_service.emit_session_snapshot(
            connection,
            request_id=request_id,
        )

    async def _handle_session_clear_history(
        self,
        connection: WebChatConnection,
        request_id: str | None,
    ) -> None:
        if connection.active_session_id is None:
            await web_chat_service.emit_error(
                connection,
                code="SESSION_REQUIRED",
                message=t("web_ui.chat.session_required"),
                request_id=request_id,
            )
            return
        principal = self._require_principal(connection)
        web_chat_service.clear_history(connection.active_session_id, principal)
        await web_chat_service.emit_session_snapshot(
            connection,
            request_id=request_id,
        )

    async def _handle_session_delete(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
    ) -> None:
        payload = SessionDeletePayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        web_chat_service.delete_session(principal, payload)
        if connection.active_session_id == payload.session_id:
            connection.active_session_id = None
        await web_chat_service.emit_session_snapshot(
            connection,
            request_id=frame.request_id,
        )

    def _require_principal(self, connection: WebChatConnection) -> "WebUIPrincipal":
        principal = connection.principal
        if principal is None:
            raise ChatAuthError(t("web_ui.chat.auth_required"))
        return principal


chat_gateway_service = ChatGatewayService()
