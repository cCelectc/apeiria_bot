"""Authentication routes for the Web UI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apeiria.infra.webui_auth.secrets import (
    get_account_by_id,
    list_security_audit_events,
    record_login_success,
    register_account,
    rotate_account_session_version,
    update_account_password,
    verify_account_password,
)
from apeiria.infra.webui_auth.service import (
    AuthSessionContext,
    auth_session_service,
)
from apeiria.interfaces.http.auth import (
    create_auth_session_token,
    require_auth,
    require_control_panel,
)
from apeiria.interfaces.http.login_guard import (
    is_login_allowed,
    record_login_failure,
)
from apeiria.interfaces.http.login_guard import (
    record_login_success as clear_login_failures,
)
from apeiria.interfaces.http.schemas.models import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    RegisterRequest,
    RegisterResponse,
    SecurityAuditEventItem,
    SessionRefreshResponse,
    WebUIAccountItem,
    WebUIPrincipalResponse,
)
from apeiria.shared.i18n import t
from apeiria.shared.principal_roles import can_access_control_panel

if TYPE_CHECKING:
    from apeiria.shared.principal import AuthSession, Principal

router = APIRouter()


def _to_webui_principal_response(principal: Principal) -> WebUIPrincipalResponse:
    return WebUIPrincipalResponse(
        user_id=principal.principal_id,
        username=principal.display_name,
        role=principal.role.role_id,
        capabilities=principal.capabilities,
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """Authenticate a Web UI account and return a JWT token."""
    client_ip = request.client.host if request.client else ""
    if not is_login_allowed(body.username, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("web_ui.auth.login_temporarily_locked"),
        )
    account = verify_account_password(body.username, body.password)
    if account is None:
        record_login_failure(body.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    if not can_access_control_panel(account.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("web_ui.auth.permission_denied"),
        )
    clear_login_failures(account.username, client_ip)
    account = record_login_success(account.user_id) or account
    session = auth_session_service.create_session(
        account,
        auth_method="password",
        context=AuthSessionContext(client_ip=client_ip),
    )
    return LoginResponse(
        token=create_auth_session_token(session),
        principal=_to_webui_principal_response(session.principal),
    )


@router.post("/register")
async def register(body: RegisterRequest) -> RegisterResponse:
    """Register a new Web UI account with a one-time registration code."""
    try:
        register_account(body.registration_code, body.username, body.password)
    except ValueError as exc:
        error_code = str(exc)
        detail_key = {
            "registration_code_invalid": "web_ui.auth.registration_code_invalid",
            "username_invalid": "web_ui.auth.username_invalid",
            "username_taken": "web_ui.auth.username_taken",
        }.get(error_code, "web_ui.auth.register_failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t(detail_key),
        ) from None
    return RegisterResponse(detail=t("web_ui.auth.register_success"))


@router.get("/me")
async def get_current_user(
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIPrincipalResponse:
    """Return the current authenticated user."""
    if not can_access_control_panel(session.role_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("web_ui.auth.permission_denied"),
        )
    return _to_webui_principal_response(session.principal)


@router.get("/me/account")
async def get_current_account(
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> WebUIAccountItem:
    """Return the current account record."""
    user_id = session.user_id
    account = get_account_by_id(user_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    return WebUIAccountItem(
        user_id=account.user_id,
        username=account.username,
        role=account.role,
        is_disabled=account.is_disabled,
        last_login_at=account.last_login_at,
        password_changed_at=account.password_changed_at,
    )


@router.get("/audit-events")
async def get_security_audit_events(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[SecurityAuditEventItem]:
    """List recent security audit events."""
    return [
        SecurityAuditEventItem(
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            actor_username=event.actor_username,
            target_username=event.target_username,
            detail=event.detail,
        )
        for event in list_security_audit_events()
    ]


@router.post("/password")
async def change_password(
    body: PasswordChangeRequest,
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> SessionRefreshResponse:
    """Change the current account password."""
    username = session.username
    user_id = session.user_id
    if body.current_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.current_password_required"),
        )
    account = verify_account_password(username, body.current_password)
    if account is None or account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    updated_account = update_account_password(user_id, body.new_password)
    if updated_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    updated_session = auth_session_service.create_session(
        updated_account,
        auth_method="session_refresh",
    )
    return SessionRefreshResponse(
        detail=t("web_ui.auth.password_changed"),
        token=create_auth_session_token(updated_session),
        principal=_to_webui_principal_response(updated_session.principal),
    )


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> SessionRefreshResponse:
    """Invalidate previous sessions and return a fresh token for the current account."""
    user_id = session.user_id
    actor_username = session.username
    updated_account = rotate_account_session_version(
        user_id,
        actor_username=actor_username,
    )
    if updated_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    updated_session = auth_session_service.create_session(
        updated_account,
        auth_method="session_refresh",
    )
    return SessionRefreshResponse(
        detail=t("web_ui.auth.sessions_revoked"),
        token=create_auth_session_token(updated_session),
        principal=_to_webui_principal_response(updated_session.principal),
    )
