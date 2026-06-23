from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from apeiria.access.principal import AuthSession  # noqa: TC001
from apeiria.i18n import t
from apeiria.webui.auth import (
    clear_auth_session_cookie,
    require_auth,
    set_auth_session_cookie,
)
from apeiria.webui.auth.accounts import (
    create_account,
    delete_account,
    get_account_by_id,
    get_account_by_username,
    list_accounts,
    reset_account_password,
    update_account_password,
)
from apeiria.webui.auth.service import auth_session_service
from apeiria.webui.auth.sessions import (
    revoke_session,
    revoke_user_sessions,
)
from apeiria.webui.auth.store import verify_password_hash
from apeiria.webui.login_guard import (
    is_login_allowed,
    record_login_failure,
    record_login_success,
)
from apeiria.webui.schemas.auth import (
    AccountCreate,
    AccountResponse,
    AuthStatusResponse,
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
    SetupRequest,
)

router = APIRouter()
_SESSION_TTL_DAYS = 7


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    client = request.client
    return client.host if client else "unknown"


def _session_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=_SESSION_TTL_DAYS)


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
) -> MessageResponse:
    client_ip = _get_client_ip(request)
    username_normalized = body.username.strip().lower()

    if not is_login_allowed(username_normalized, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=t("web_ui.auth.login_throttled"),
        )

    account = await get_account_by_username(body.username)
    if account is None or not verify_password_hash(
        body.password, account.password_hash
    ):
        record_login_failure(username_normalized, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )

    session_id, _auth_session = await auth_session_service.create_session(
        account,
        auth_method="session_cookie",
        client_ip=client_ip,
    )
    expires_at = _session_expires_at()
    set_auth_session_cookie(
        response, session_id, expires_at=expires_at, request=request
    )
    record_login_success(username_normalized, client_ip)
    return MessageResponse(detail="ok")


@router.post("/logout")
async def logout(
    response: Response,
    _auth: Annotated[AuthSession, Depends(require_auth)],
    request: Request,
) -> MessageResponse:
    session_id = request.cookies.get("apeiria_webui_session", "").strip()
    if session_id:
        await revoke_session(session_id)
    clear_auth_session_cookie(response)
    return MessageResponse(detail="ok")


@router.get("/me", response_model=MeResponse)
async def me(
    auth: Annotated[AuthSession, Depends(require_auth)],
) -> MeResponse:
    return MeResponse(user_id=auth.user_id, username=auth.username)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    auth: Annotated[AuthSession, Depends(require_auth)],
    request: Request,
) -> MessageResponse:
    account = await get_account_by_id(auth.user_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    if not verify_password_hash(body.current_password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )

    await update_account_password(auth.user_id, body.new_password)

    session_id = request.cookies.get("apeiria_webui_session", "").strip()
    await revoke_user_sessions(auth.user_id, except_session_id=session_id or None)

    return MessageResponse(detail="ok")


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status() -> AuthStatusResponse:
    accounts = await list_accounts()
    return AuthStatusResponse(has_accounts=len(accounts) > 0)


@router.post("/setup", response_model=MeResponse, status_code=201)
async def setup(
    body: SetupRequest,
    response: Response,
    request: Request,
) -> MeResponse:
    accounts = await list_accounts()
    if accounts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t("web_ui.auth.setup_not_allowed"),
        )

    username = await create_account(body.username, body.password)
    account = await get_account_by_username(username)
    if account is None:
        raise HTTPException(status_code=500, detail="account_not_found_after_create")

    session_id, _auth_session = await auth_session_service.create_session(
        account,
        auth_method="session_cookie",
    )
    expires_at = _session_expires_at()
    set_auth_session_cookie(
        response, session_id, expires_at=expires_at, request=request
    )

    return MeResponse(user_id=account.user_id, username=account.username)


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts_route(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AccountResponse]:
    return [
        AccountResponse(id=a.user_id, username=a.username, created_at="")
        for a in await list_accounts()
    ]


@router.post("/accounts", response_model=AccountResponse, status_code=201)
async def create_account_route(
    body: AccountCreate,
    _: Annotated[Any, Depends(require_auth)],
) -> AccountResponse:
    username = await create_account(body.username, body.password)
    account = await get_account_by_username(username)
    if account is None:
        raise HTTPException(status_code=500, detail="account_not_found_after_create")
    return AccountResponse(id=account.user_id, username=account.username, created_at="")


@router.delete("/accounts/{user_id}")
async def delete_account_route(
    user_id: str,
    auth: Annotated[AuthSession, Depends(require_auth)],
) -> MessageResponse:
    if user_id == auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.self_delete_forbidden"),
        )

    await revoke_user_sessions(user_id)

    success = await delete_account(user_id, actor_user_id=auth.user_id)
    if not success:
        raise HTTPException(status_code=404, detail=t("web_ui.auth.account_not_found"))
    return MessageResponse(detail="ok")


@router.post("/accounts/{user_id}/disable")
async def disable_account(
    user_id: str,
    auth: Annotated[AuthSession, Depends(require_auth)],
) -> MessageResponse:
    if user_id == auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("web_ui.auth.self_disable_forbidden"),
        )
    account = await get_account_by_id(user_id)
    if account is None:
        raise HTTPException(status_code=404, detail=t("web_ui.auth.account_not_found"))

    await revoke_user_sessions(user_id)

    return MessageResponse(detail="ok")


@router.post("/accounts/{user_id}/reset-password")
async def reset_password_route(
    user_id: str,
    body: ResetPasswordRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> MessageResponse:
    account = await reset_account_password(user_id, body.password)
    if account is None:
        raise HTTPException(status_code=404, detail=t("web_ui.auth.account_not_found"))

    await revoke_user_sessions(user_id)

    return MessageResponse(detail="ok")
