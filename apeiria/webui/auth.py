"""HTTP auth dependencies built on top of formal auth sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, Response, status

from apeiria.access.principal import AuthSession  # noqa: TC001
from apeiria.access.principal_roles import (
    CAP_ACCOUNT_MANAGE,
    CAP_CONTROL_PANEL,
    ROLE_OWNER,
    normalize_role,
)
from apeiria.app.access.webui_auth.service import auth_session_service
from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import HTTPConnection

_AUTH_COOKIE_NAME = "apeiria_webui_session"


def _verify_auth_session_token(token: str) -> AuthSession:
    """Verify one JWT token and return the structured auth session."""

    try:
        return auth_session_service.verify_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_expired"),
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        ) from None


def set_auth_session_cookie(
    response: Response,
    session: AuthSession,
    *,
    request: Request | None = None,
) -> None:
    """Persist the session token in a browser-managed HttpOnly cookie."""

    token = auth_session_service.create_token(session)
    response.set_cookie(
        _AUTH_COOKIE_NAME,
        token,
        httponly=True,
        secure=_request_is_secure(request),
        samesite="lax",
        expires=session.expires_at,
        path="/",
    )


def clear_auth_session_cookie(response: Response) -> None:
    """Clear the browser-managed auth session cookie."""

    response.delete_cookie(
        _AUTH_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        path="/",
    )


async def require_auth(
    request: Request,
) -> AuthSession:
    """Require a valid browser session cookie."""

    token = _session_token_from_cookie(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    return _verify_auth_session_token(token)


async def require_connection_auth(connection: "HTTPConnection") -> AuthSession:
    """Require a valid browser session cookie on HTTP or WebSocket connections."""

    token = _session_token_from_cookie(connection)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    return _verify_auth_session_token(token)


def _session_token_from_cookie(connection: "HTTPConnection") -> str:
    """Read the current auth token from the browser-managed session cookie."""

    return connection.cookies.get(_AUTH_COOKIE_NAME, "").strip()


def _request_is_secure(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.split(",", 1)[0].strip().lower() == "https":
        return True
    return request.url.scheme == "https"


def require_role(required_role: str) -> Callable[..., Any]:
    """Build a dependency that requires the current session role."""

    async def _require_role(
        session: Annotated[AuthSession, Depends(require_auth)],
    ) -> AuthSession:
        actual_role = normalize_role(session.role_id)
        if actual_role != normalize_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=t("web_ui.auth.permission_denied"),
            )
        return session

    return _require_role


require_owner = require_role(ROLE_OWNER)


def require_capability(capability: str) -> Callable[..., Any]:
    """Build a dependency that requires one control-panel capability."""

    async def _require_capability(
        session: Annotated[AuthSession, Depends(require_auth)],
    ) -> AuthSession:
        if not session.has_capability(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=t("web_ui.auth.permission_denied"),
            )
        return session

    return _require_capability


require_control_panel = require_capability(CAP_CONTROL_PANEL)
require_account_manage = require_capability(CAP_ACCOUNT_MANAGE)
