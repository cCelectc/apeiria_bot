"""Web UI auth session services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.access.principal import AuthMethod, AuthSession
from apeiria.access.principal_service import principal_service
from apeiria.webui.auth.sessions import (
    SessionNotFoundError,
    create_session,
    verify_session,
)

if TYPE_CHECKING:
    from apeiria.webui.auth.accounts import WebUIAccount


class AuthSessionService:
    """Create and verify database-backed auth sessions."""

    async def create_session(
        self,
        account: "WebUIAccount",
        *,
        auth_method: AuthMethod,
        client_ip: str | None = None,
    ) -> tuple[str, AuthSession]:
        session_id = await create_session(
            user_id=account.user_id,
        )

        now = datetime.now(timezone.utc)
        principal = principal_service.build_webui_account_principal(
            user_id=account.user_id,
            username=account.username,
        )
        auth_session = AuthSession(
            principal=principal,
            auth_method=auth_method,
            token_subject=account.username,
            issued_at=now,
            expires_at=None,
            client_ip=client_ip,
        )
        return session_id, auth_session

    async def verify_session(self, session_id: str) -> AuthSession:
        record = await verify_session(session_id)

        user_id = record.user_id
        from apeiria.webui.auth.accounts import get_account_by_id

        account = await get_account_by_id(user_id)
        if account is None:
            raise SessionNotFoundError

        principal = principal_service.build_webui_account_principal(
            user_id=account.user_id,
            username=account.username,
        )
        return AuthSession(
            principal=principal,
            auth_method="session_cookie",
            token_subject=account.username,
            issued_at=datetime.now(timezone.utc),
            expires_at=None,
        )


auth_session_service = AuthSessionService()
