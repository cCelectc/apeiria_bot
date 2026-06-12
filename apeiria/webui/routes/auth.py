"""Authentication and account-management routes for the Web UI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from apeiria.app.access.webui_auth.secrets import (
    create_account,
    delete_account,
    get_account_by_id,
    list_accounts,
    record_login_success,
    reset_account_password,
    rotate_account_session_version,
    set_account_disabled,
    update_account_password,
    verify_account_password,
)
from apeiria.app.access.webui_auth.service import (
    AuthSessionContext,
    auth_session_service,
)
from apeiria.i18n import t
from apeiria.utils.project_context import current_project_root
from apeiria.webui.auth import (
    clear_auth_session_cookie,
    require_auth,
    set_auth_session_cookie,
)
from apeiria.webui.frontend_build import frontend_workspace_name
from apeiria.webui.login_guard import (
    is_login_allowed,
    record_login_failure,
)
from apeiria.webui.login_guard import (
    record_login_success as clear_login_failures,
)
from apeiria.webui.schemas.models import (
    AccountCreateRequest,
    AccountDeleteRequest,
    AccountDisableRequest,
    AccountPasswordResetRequest,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    RegisterResponse,
    SessionRefreshResponse,
    WebUIAccountItem,
    WebUIBootstrapResponse,
    WebUILocaleItem,
    WebUIPrincipalResponse,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession, Principal
else:
    AuthSession = Any
    Principal = Any

router = APIRouter()


def _to_webui_principal_response(principal: Principal) -> WebUIPrincipalResponse:
    return WebUIPrincipalResponse(
        user_id=principal.principal_id,
        username=principal.display_name,
    )


def _to_webui_account_item(account: Any) -> WebUIAccountItem:
    return WebUIAccountItem(
        user_id=account.user_id,
        username=account.username,
        is_disabled=account.is_disabled,
        last_login_at=account.last_login_at,
        password_changed_at=account.password_changed_at,
    )


async def _require_actor_password(
    session: "AuthSession",
    actor_password: str,
) -> None:
    account = await verify_account_password(session.username, actor_password)
    if account is None or account.user_id != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.invalid_credentials"),
        )


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
) -> LoginResponse:
    """Authenticate a Web UI account and establish a browser session."""
    client_ip = request.client.host if request.client else ""
    if not is_login_allowed(body.username, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("web_ui.auth.login_temporarily_locked"),
        )
    account = await verify_account_password(body.username, body.password)
    if account is None:
        record_login_failure(body.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    clear_login_failures(account.username, client_ip)
    account = await record_login_success(account.user_id) or account
    session = auth_session_service.create_session(
        account,
        auth_method="password",
        context=AuthSessionContext(client_ip=client_ip),
    )
    await set_auth_session_cookie(response, session, request=request)
    return LoginResponse(
        principal=_to_webui_principal_response(session.principal),
    )


@router.post("/logout")
async def logout(response: Response) -> RegisterResponse:
    """Clear the current browser-managed Web UI session."""
    clear_auth_session_cookie(response)
    return RegisterResponse(detail=t("web_ui.auth.logout_success"))


@router.get("/me")
async def get_current_user(
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIPrincipalResponse:
    """Return the current authenticated user."""
    return _to_webui_principal_response(session.principal)


@router.get("/bootstrap", response_model=WebUIBootstrapResponse)
async def get_webui_bootstrap(
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIBootstrapResponse:
    account = await get_account_by_id(session.user_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    return WebUIBootstrapResponse(
        principal=_to_webui_principal_response(session.principal),
        account=_to_webui_account_item(account),
        locales=[
            WebUILocaleItem(code="zh_CN", label="中文"),
            WebUILocaleItem(code="en_US", label="English"),
        ],
        preferred_home="/dashboard",
        frontend_workspace=frontend_workspace_name(current_project_root()),
    )


@router.get("/accounts", response_model=list[WebUIAccountItem])
async def get_accounts(
    _: Annotated[AuthSession, Depends(require_auth)],
) -> list[WebUIAccountItem]:
    """Return all account records."""
    return [_to_webui_account_item(account) for account in await list_accounts()]


@router.post("/accounts", response_model=WebUIAccountItem)
async def create_managed_account(
    body: AccountCreateRequest,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIAccountItem:
    await _require_actor_password(session, body.actor_password)
    try:
        normalized_username = await create_account(body.username, body.password)
    except ValueError as exc:
        error_code = str(exc)
        detail_key = {
            "username_invalid": "web_ui.auth.username_invalid",
            "username_taken": "web_ui.auth.username_taken",
            "password_invalid": "web_ui.auth.invalid_credentials",
        }.get(error_code, "web_ui.auth.invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t(detail_key),
        ) from None
    all_accounts = await list_accounts()
    account = next(
        (item for item in all_accounts if item.username == normalized_username),
        None,
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="account_create_failed",
        )
    return _to_webui_account_item(account)


@router.patch("/accounts/{user_id}", response_model=WebUIAccountItem)
async def update_managed_account_status(
    user_id: str,
    body: AccountDisableRequest,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIAccountItem:
    await _require_actor_password(session, body.actor_password)
    try:
        account = await set_account_disabled(
            user_id,
            disabled=body.is_disabled,
            actor_user_id=session.user_id,
        )
    except ValueError as exc:
        detail_key = {
            "self_disable_forbidden": "web_ui.auth.self_disable_forbidden",
            "last_account_forbidden": "web_ui.auth.last_account_forbidden",
        }.get(str(exc), "web_ui.auth.invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t(detail_key),
        ) from None
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    return _to_webui_account_item(account)


@router.delete("/accounts/{user_id}", response_model=RegisterResponse)
async def delete_managed_account(
    user_id: str,
    body: AccountDeleteRequest,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> RegisterResponse:
    await _require_actor_password(session, body.actor_password)
    try:
        deleted = await delete_account(user_id, actor_user_id=session.user_id)
    except ValueError as exc:
        detail_key = {
            "self_delete_forbidden": "web_ui.auth.self_delete_forbidden",
            "last_account_forbidden": "web_ui.auth.last_account_forbidden",
        }.get(str(exc), "web_ui.auth.invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t(detail_key),
        ) from None
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    return RegisterResponse(detail=t("web_ui.auth.account_deleted"))


@router.post("/accounts/{user_id}/reset-password", response_model=WebUIAccountItem)
async def reset_managed_account_password(
    user_id: str,
    body: AccountPasswordResetRequest,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> WebUIAccountItem:
    await _require_actor_password(session, body.actor_password)
    if user_id == session.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.self_password_reset_forbidden"),
        )
    try:
        account = await reset_account_password(user_id, body.new_password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.invalid_credentials"),
        ) from None
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    return _to_webui_account_item(account)


@router.post("/password")
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> SessionRefreshResponse:
    """Change the current account password."""
    username = session.username
    user_id = session.user_id
    if body.current_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.current_password_required"),
        )
    account = await verify_account_password(username, body.current_password)
    if account is None or account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    updated_account = await update_account_password(user_id, body.new_password)
    if updated_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    updated_session = auth_session_service.create_session(
        updated_account,
        auth_method="session_refresh",
    )
    await set_auth_session_cookie(response, updated_session, request=request)
    return SessionRefreshResponse(
        detail=t("web_ui.auth.password_changed"),
        principal=_to_webui_principal_response(updated_session.principal),
    )


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    request: Request,
    response: Response,
    session: Annotated[AuthSession, Depends(require_auth)],
) -> SessionRefreshResponse:
    """Invalidate previous sessions and rotate the current account session."""
    updated_account = await rotate_account_session_version(session.user_id)
    if updated_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t("web_ui.auth.account_not_found"),
        )
    updated_session = auth_session_service.create_session(
        updated_account,
        auth_method="session_refresh",
    )
    await set_auth_session_cookie(response, updated_session, request=request)
    return SessionRefreshResponse(
        detail=t("web_ui.auth.sessions_revoked"),
        principal=_to_webui_principal_response(updated_session.principal),
    )
