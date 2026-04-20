"""HTTP auth dependencies built on top of formal auth sessions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apeiria.access.principal import AuthSession  # noqa: TC001
from apeiria.access.principal_roles import (
    CAP_ACCOUNT_MANAGE,
    CAP_CONTROL_PANEL,
    ROLE_OWNER,
    normalize_role,
)
from apeiria.access.webui_auth.service import auth_session_service
from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable

_security = HTTPBearer()


def create_auth_session_token(session: AuthSession) -> str:
    """Create a JWT token for one authenticated session."""

    return auth_session_service.create_token(session)


def verify_auth_session_token(token: str) -> AuthSession:
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


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
) -> AuthSession:
    """Require a valid JWT bearer token."""

    return verify_auth_session_token(credentials.credentials)


async def require_optional_auth(request: Request) -> AuthSession:
    """Require a bearer token when headers are handled manually."""

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )
    return verify_auth_session_token(token)


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
