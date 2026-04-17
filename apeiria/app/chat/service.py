"""Application service for Web UI chat gateway flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.chat.protocol import (
    AuthHelloPayload,
    ChatEnvelope,
    MessageSendPayload,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionUpdatePayload,
)
from apeiria.app.chat.web_chat import WebChatConnection, web_chat_service
from apeiria.shared.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.app.chat.web_chat.assets import ChatAsset
    from apeiria.app.chat.web_chat.protocol import WebUIPrincipal
    from apeiria.shared.principal import AuthSession


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
        active_session_id: str | None,
        token_verifier: Callable[[str], "AuthSession"],
    ) -> str | None:
        if frame.type != "auth.hello" and connection.principal is None:
            await web_chat_service.emit_error(
                connection,
                code="AUTH_REQUIRED",
                message=t("web_ui.chat.auth_required"),
                request_id=frame.request_id,
            )
            return active_session_id

        if frame.type == "auth.hello":
            return await self._handle_auth_hello(
                connection,
                frame,
                token_verifier,
                active_session_id,
            )
        if frame.type == "capabilities.request":
            await web_chat_service.emit_capabilities(
                connection,
                request_id=frame.request_id,
            )
            return active_session_id
        if frame.type in {
            "session.create",
            "session.update",
            "session.list",
            "session.close",
            "session.clear_history",
            "session.delete",
        }:
            return await self._handle_session_frame(
                connection,
                frame,
                active_session_id,
            )
        if frame.type == "message.send":
            return await self._handle_message_send(
                connection,
                frame,
                active_session_id,
            )
        await web_chat_service.emit_error(
            connection,
            code="UNSUPPORTED_FRAME",
            message=t("web_ui.chat.unsupported_frame", type=frame.type),
            request_id=frame.request_id,
        )
        return active_session_id

    async def _handle_session_frame(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        active_session_id: str | None,
    ) -> str | None:
        next_session_id = active_session_id
        match frame.type:
            case "session.create":
                next_session_id = await self._handle_session_create(
                    connection,
                    frame,
                    active_session_id,
                )
            case "session.update":
                next_session_id = await self._handle_session_update(
                    connection,
                    frame,
                    active_session_id,
                )
            case "session.list":
                principal = self._require_principal(connection)
                await web_chat_service.emit_session_list(
                    connection,
                    principal,
                    request_id=frame.request_id,
                )
            case "session.close":
                next_session_id = await self._handle_session_close(
                    connection,
                    active_session_id,
                )
            case "session.clear_history":
                await self._handle_session_clear_history(
                    connection,
                    active_session_id,
                    frame.request_id,
                )
            case "session.delete":
                next_session_id = await self._handle_session_delete(
                    connection,
                    frame,
                    active_session_id,
                )
        return next_session_id

    async def _handle_session_create(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        active_session_id: str | None,
    ) -> str | None:
        payload = SessionCreatePayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        session = web_chat_service.create_session(principal, payload)
        active_session_id = session.session_id
        await web_chat_service.emit_session_state(
            connection,
            session,
            request_id=frame.request_id,
        )
        await web_chat_service.emit_session_list(connection, principal)
        return active_session_id

    async def _handle_session_update(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        active_session_id: str | None,
    ) -> str | None:
        payload = SessionUpdatePayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        session = web_chat_service.update_session(principal, payload)
        active_session_id = session.session_id
        await web_chat_service.emit_session_state(
            connection,
            session,
            request_id=frame.request_id,
        )
        await web_chat_service.emit_session_list(connection, principal)
        return active_session_id

    async def _handle_message_send(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        active_session_id: str | None,
    ) -> str | None:
        payload = MessageSendPayload.model_validate(frame.payload)
        await web_chat_service.handle_message(connection, payload)
        principal = self._require_principal(connection)
        await web_chat_service.emit_session_list(connection, principal)
        return active_session_id

    async def _handle_auth_hello(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        token_verifier: Callable[[str], "AuthSession"],
        active_session_id: str | None,
    ) -> str | None:
        try:
            payload = AuthHelloPayload.model_validate(frame.payload)
            session = token_verifier(payload.token)
            principal = web_chat_service.build_principal(session)
            await web_chat_service.emit_auth_ok(
                connection,
                principal,
                request_id=frame.request_id,
            )
            await web_chat_service.emit_system_info(
                connection,
                t("web_ui.chat.auth_connected"),
            )
            await web_chat_service.emit_session_list(connection, principal)
        except ChatAuthError as exc:
            await web_chat_service.emit_error(
                connection,
                code="AUTH_FAILED",
                message=str(exc),
                request_id=frame.request_id,
                type_="auth.error",
            )
        return active_session_id

    async def _handle_session_close(
        self,
        connection: WebChatConnection,
        active_session_id: str | None,
    ) -> str | None:
        if active_session_id is None:
            return None
        principal = self._require_principal(connection)
        web_chat_service.close_session(active_session_id)
        await web_chat_service.emit_session_list(connection, principal)
        return None

    async def _handle_session_clear_history(
        self,
        connection: WebChatConnection,
        active_session_id: str | None,
        request_id: str | None,
    ) -> None:
        if active_session_id is None:
            await web_chat_service.emit_error(
                connection,
                code="SESSION_REQUIRED",
                message=t("web_ui.chat.session_required"),
                request_id=request_id,
            )
            return
        principal = self._require_principal(connection)
        session = web_chat_service.clear_history(active_session_id, principal)
        await web_chat_service.emit_session_state(
            connection,
            session,
            request_id=request_id,
        )
        await web_chat_service.emit_session_list(connection, principal)

    async def _handle_session_delete(
        self,
        connection: WebChatConnection,
        frame: ChatEnvelope,
        active_session_id: str | None,
    ) -> str | None:
        payload = SessionDeletePayload.model_validate(frame.payload)
        principal = self._require_principal(connection)
        web_chat_service.delete_session(principal, payload)
        await web_chat_service.emit_session_deleted(
            connection,
            payload.session_id,
            request_id=frame.request_id,
        )
        await web_chat_service.emit_session_list(connection, principal)
        if active_session_id == payload.session_id:
            return None
        return active_session_id

    def _require_principal(self, connection: WebChatConnection) -> "WebUIPrincipal":
        principal = connection.principal
        if principal is None:
            raise ChatAuthError(t("web_ui.chat.auth_required"))
        return principal


chat_gateway_service = ChatGatewayService()
