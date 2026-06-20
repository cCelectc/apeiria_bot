from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

from apeiria.db.engine import get_session
from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.access.principal import AuthSession

_ACCESS_COOKIE = "apeiria_webui_access"
_REFRESH_COOKIE = "apeiria_webui_refresh"


def _read_access_token(request: Request) -> str:
    return request.cookies.get(_ACCESS_COOKIE, "").strip()


async def require_auth(request: Request) -> "AuthSession":
    import jwt

    from apeiria.webui.auth.service import auth_session_service

    token = _read_access_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    try:
        return await auth_session_service.verify_token(token)
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


async def get_db() -> AsyncIterator["AsyncSession"]:
    async with get_session() as db:
        yield db


def _request_is_secure(request: Request | None) -> bool:
    if request is None:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.split(",", 1)[0].strip().lower() == "https":
        return True
    return request.url.scheme == "https"
