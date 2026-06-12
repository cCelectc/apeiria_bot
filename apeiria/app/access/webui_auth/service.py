"""Web UI auth session services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import jwt

from apeiria.access.principal import AuthMethod, AuthSession
from apeiria.access.principal_service import principal_service
from apeiria.app.access.webui_auth.secrets import get_account_by_id, get_token_secret
from apeiria.config.webui_config import get_web_ui_config

if TYPE_CHECKING:
    from apeiria.app.access.webui_auth.secrets import WebUIAccount


@dataclass(frozen=True)
class AuthSessionContext:
    token_subject: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    client_ip: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)


class AuthSessionService:
    """Create and verify JWT-backed auth sessions."""

    def create_session(
        self,
        account: "WebUIAccount",
        *,
        auth_method: AuthMethod,
        context: AuthSessionContext | None = None,
    ) -> AuthSession:
        resolved_context = context or AuthSessionContext()
        resolved_issued_at = resolved_context.issued_at or datetime.now(timezone.utc)
        resolved_expires_at = (
            resolved_context.expires_at
            or resolved_issued_at
            + timedelta(days=get_web_ui_config().token_expire_days)
        )
        principal = principal_service.build_webui_account_principal(
            user_id=account.user_id,
            username=account.username,
        )
        return AuthSession(
            principal=principal,
            auth_method=auth_method,
            session_version=account.session_version,
            token_subject=resolved_context.token_subject or account.username,
            issued_at=resolved_issued_at,
            expires_at=resolved_expires_at,
            client_ip=resolved_context.client_ip,
            attributes=dict(resolved_context.attributes),
        )

    async def create_token(self, session: AuthSession) -> str:
        payload = {
            "exp": session.expires_at,
            "iat": session.issued_at,
            "sub": session.token_subject,
            "user_id": session.user_id,
            "username": session.username,
            "session_version": session.session_version,
            "auth_method": session.auth_method,
            "client_ip": session.client_ip,
            **session.attributes,
        }
        secret = await get_token_secret()
        return jwt.encode(payload, secret, algorithm="HS256")

    async def verify_token(self, token: str) -> AuthSession:
        secret = await get_token_secret()
        claims = jwt.decode(token, secret, algorithms=["HS256"])
        user_id = str(claims.get("user_id") or "")
        account = await get_account_by_id(user_id) if user_id else None
        if account is None or account.is_disabled:
            raise jwt.InvalidTokenError
        token_session_version = int(claims.get("session_version") or 0)
        if token_session_version != account.session_version:
            raise jwt.InvalidTokenError

        return self.create_session(
            account,
            auth_method="session_cookie",
            context=AuthSessionContext(
                client_ip=self._coerce_string(claims.get("client_ip")),
                token_subject=str(claims.get("sub") or account.username),
                issued_at=self._coerce_datetime(claims.get("iat")),
                expires_at=self._coerce_datetime(claims.get("exp")),
                attributes={
                    str(key): cast("object", value)
                    for key, value in claims.items()
                    if key
                    not in {
                        "exp",
                        "iat",
                        "sub",
                        "user_id",
                        "username",
                        "session_version",
                        "auth_method",
                        "client_ip",
                    }
                },
            ),
        )

    def _coerce_datetime(self, value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return None

    def _coerce_string(self, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        return value


auth_session_service = AuthSessionService()
