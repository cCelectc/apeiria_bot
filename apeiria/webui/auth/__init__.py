"""HTTP auth dependencies built on top of formal auth sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Response, status

from apeiria.access.principal import AuthSession  # noqa: TC001
from apeiria.i18n import t
from apeiria.webui.auth.service import auth_session_service
from apeiria.webui.auth.sessions import (
    SessionExpiredError,
    SessionNotFoundError,
    SessionRevokedError,
)

if TYPE_CHECKING:
    from datetime import datetime

    from starlette.requests import HTTPConnection

_AUTH_COOKIE_NAME = "apeiria_webui_session"


async def set_auth_session_cookie(
    response: Response,
    session_id: str,
    *,
    expires_at: datetime,
    request: Request | None = None,
) -> None:
    response.set_cookie(
        _AUTH_COOKIE_NAME,
        session_id,
        httponly=True,
        secure=_request_is_secure(request),
        samesite="lax",
        expires=expires_at,
        path="/",
    )


def clear_auth_session_cookie(response: Response) -> None:
    response.delete_cookie(
        _AUTH_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        path="/",
    )


async def require_auth(
    request: Request,
) -> AuthSession:
    session_id = _session_id_from_cookie(request)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    try:
        return await auth_session_service.verify_session(session_id)
    except SessionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_expired"),
        ) from None
    except (SessionNotFoundError, SessionRevokedError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        ) from None


async def require_connection_auth(connection: "HTTPConnection") -> AuthSession:
    session_id = _session_id_from_cookie(connection)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    try:
        return await auth_session_service.verify_session(session_id)
    except SessionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_expired"),
        ) from None
    except (SessionNotFoundError, SessionRevokedError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        ) from None


def _session_id_from_cookie(connection: "HTTPConnection") -> str:
    return connection.cookies.get(_AUTH_COOKIE_NAME, "").strip()


def _request_is_secure(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.split(",", 1)[0].strip().lower() == "https":
        return True
    return request.url.scheme == "https"
