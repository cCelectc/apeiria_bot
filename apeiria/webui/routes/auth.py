from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update

from apeiria.db.engine import get_session
from apeiria.db.models.auth import RefreshToken as RefreshTokenModel
from apeiria.i18n import t
from apeiria.webui.auth.accounts import (
    create_account,
    delete_account,
    get_account_by_id,
    get_account_by_username,
    reset_account_password,
    update_account_password,
)
from apeiria.webui.auth.service import (
    AuthSessionContext,
    auth_session_service,
)
from apeiria.webui.auth.store import iso_now, verify_password_hash
from apeiria.webui.routes.deps import (
    _ACCESS_COOKIE,
    _REFRESH_COOKIE,
    _request_is_secure,
    require_auth,
)
from apeiria.webui.schemas.auth import (
    AccountCreate,
    AccountResponse,
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession

router = APIRouter()
_ACCESS_TTL_MINUTES = 15
_REFRESH_TTL_DAYS = 7
_REFRESH_TOKEN_BYTES = 64


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _set_auth_cookies(  # noqa: PLR0913
    response: Response,
    access_token: str,
    access_expires: datetime,
    refresh_token: str,
    refresh_expires: datetime,
    *,
    request: Request | None = None,
) -> None:
    secure = _request_is_secure(request)
    response.set_cookie(
        _ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        expires=access_expires,
        path="/api",
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        expires=refresh_expires,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (_ACCESS_COOKIE, _REFRESH_COOKIE):
        response.delete_cookie(name, httponly=True, samesite="lax", path="/")


async def _create_refresh_token(
    db: Any,
    user_id: int,
) -> tuple[str, RefreshTokenModel]:
    raw = secrets.token_hex(_REFRESH_TOKEN_BYTES)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS)
    ).isoformat()
    row = RefreshTokenModel(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return raw, row


async def _revoke_user_refresh_tokens(db: Any, user_id: int) -> None:
    await db.execute(
        update(RefreshTokenModel)
        .where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked == 0,
        )
        .values(revoked=1)
    )


async def _build_access_session(account: Any) -> AuthSession:
    now = datetime.now(timezone.utc)
    return auth_session_service.create_session(
        account,
        auth_method="session_cookie",
        context=AuthSessionContext(
            issued_at=now,
            expires_at=now + timedelta(minutes=_ACCESS_TTL_MINUTES),
        ),
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
) -> MessageResponse:
    account = await get_account_by_username(body.username)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )
    if not verify_password_hash(body.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.invalid_credentials"),
        )

    session = await _build_access_session(account)
    access_token = await auth_session_service.create_token(session)

    async with get_session() as db:
        raw_refresh, _ = await _create_refresh_token(db, int(account.user_id))
        await db.commit()

    refresh_expires = datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS)
    _set_auth_cookies(
        response,
        access_token,
        session.expires_at or datetime.now(timezone.utc),
        raw_refresh,
        refresh_expires,
        request=request,
    )
    return MessageResponse(detail="ok")


@router.post("/logout")
async def logout(
    response: Response,
    _: Annotated[Any, Depends(require_auth)],
) -> MessageResponse:
    _clear_auth_cookies(response)
    return MessageResponse(detail="ok")


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
) -> MessageResponse:
    raw_token = request.cookies.get(_REFRESH_COOKIE, "").strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("web_ui.auth.token_invalid"),
        )

    token_hash = _hash_token(raw_token)

    async with get_session() as db:
        row = (
            await db.execute(
                select(RefreshTokenModel).where(
                    RefreshTokenModel.token_hash == token_hash,
                    RefreshTokenModel.revoked == 0,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=t("web_ui.auth.token_invalid"),
            )

        if row.expires_at < iso_now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=t("web_ui.auth.token_expired"),
            )

        await db.delete(row)

        account = await get_account_by_id(str(row.user_id))
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=t("web_ui.auth.token_invalid"),
            )

        session = await _build_access_session(account)
        access_token = await auth_session_service.create_token(session)
        raw_refresh, _ = await _create_refresh_token(db, int(account.user_id))
        await db.commit()

    refresh_expires = datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS)
    _set_auth_cookies(
        response,
        access_token,
        session.expires_at or datetime.now(timezone.utc),
        raw_refresh,
        refresh_expires,
        request=request,
    )
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

    async with get_session() as db:
        await _revoke_user_refresh_tokens(db, int(auth.user_id))
        await db.commit()

    return MessageResponse(detail="ok")


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AccountResponse]:
    from apeiria.webui.auth.accounts import list_accounts as _list_accounts

    return [
        AccountResponse(id=a.user_id, username=a.username, created_at="")
        for a in await _list_accounts()
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
    async with get_session() as db:
        await _revoke_user_refresh_tokens(db, int(user_id))
        await db.commit()

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

    async with get_session() as db:
        await _revoke_user_refresh_tokens(db, int(user_id))
        await db.commit()

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

    async with get_session() as db:
        await _revoke_user_refresh_tokens(db, int(user_id))
        await db.commit()

    return MessageResponse(detail="ok")
