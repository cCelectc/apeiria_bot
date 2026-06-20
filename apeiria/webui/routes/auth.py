from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.auth import WebUIAccount
from apeiria.webui.auth import (
    clear_auth_session_cookie,
    require_auth,
    set_auth_session_cookie,
)
from apeiria.webui.auth.accounts import (
    WebUIAccount as WebUIAccountDC,
)
from apeiria.webui.auth.accounts import (
    get_account_by_id,
    get_account_by_username,
    reset_account_password,
)
from apeiria.webui.auth.service import auth_session_service
from apeiria.webui.auth.store import (
    hash_password,
    iso_now,
    verify_password_hash,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class LoginResponse(BaseModel):
    success: bool
    must_change_password: bool = False
    principal: dict | None = None


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    account = await get_account_by_username(body.username)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password_hash(body.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session = auth_session_service.create_session(
        account,
        auth_method="password",
    )
    await set_auth_session_cookie(response, session)

    async with get_session() as db:
        acc = (
            await db.execute(
                select(WebUIAccount).where(WebUIAccount.id == int(account.user_id))
            )
        ).scalar_one_or_none()

    return LoginResponse(
        success=True,
        must_change_password=bool(acc.must_change_password) if acc else False,
        principal={
            "user_id": account.user_id,
            "username": account.username,
        },
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_auth_session_cookie(response)
    return {"success": True}


@router.get("/me")
async def me(
    _session: Annotated[Any, Depends(require_auth)],
) -> dict:
    return {
        "id": _session.user_id,
        "user_id": _session.user_id,
        "username": _session.username,
        "role": "admin",
    }


@router.post("/change_password")
async def change_password(
    body: ChangePasswordRequest,
    _session: Annotated[Any, Depends(require_auth)],
) -> dict:
    account = await get_account_by_id(_session.user_id)
    if account is None:
        raise HTTPException(status_code=401)

    if not verify_password_hash(body.current_password, account.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Current password incorrect",
        )

    new_hash = hash_password(body.new_password)

    async with get_session() as db:
        acc = (
            await db.execute(
                select(WebUIAccount).where(WebUIAccount.id == int(account.user_id))
            )
        ).scalar_one_or_none()
        if not acc:
            raise HTTPException(status_code=401)
        acc.password_hash = new_hash
        acc.password_changed_at = iso_now()
        acc.must_change_password = 0
        await db.commit()

    return {"success": True}


class ResetPasswordRequest(BaseModel):
    new_password: str
    actor_password: str


@router.post("/accounts/{user_id}/reset-password")
async def route_reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    _session: Annotated[Any, Depends(require_auth)],
) -> WebUIAccountDC:
    actor = await get_account_by_id(_session.user_id)
    if actor is None:
        raise HTTPException(status_code=401)
    if not verify_password_hash(body.actor_password, actor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid actor password")
    return await reset_account_password(user_id, body.new_password)


class AccountDeleteRequest(BaseModel):
    actor_password: str


@router.delete("/accounts/{user_id}")
async def route_delete_account(
    user_id: str,
    body: AccountDeleteRequest,
    _session: Annotated[Any, Depends(require_auth)],
) -> dict:
    actor = await get_account_by_id(_session.user_id)
    if actor is None:
        raise HTTPException(status_code=401)
    if not verify_password_hash(body.actor_password, actor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid actor password")

    from apeiria.webui.auth.accounts import delete_account

    ok = await delete_account(user_id, actor_user_id=_session.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted"}


@router.post("/accounts/{user_id}/disable")
async def route_disable_account(
    user_id: str,
    _session: Annotated[Any, Depends(require_auth)],
) -> dict:
    if _session.user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot disable self")
    async with get_session() as db:
        acc = (
            await db.execute(
                select(WebUIAccount).where(WebUIAccount.id == int(user_id))
            )
        ).scalar_one_or_none()
        if not acc:
            raise HTTPException(status_code=404, detail="Not found")
        await db.delete(acc)
        await db.commit()
    return {"status": "disabled"}
