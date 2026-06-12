"""Web UI account lifecycle."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, update

from apeiria.app.access.webui_auth.store import (
    count_enabled_accounts,
    hash_password,
    iso_now,
    list_user_items,
    load_store_data_readonly,
    normalize_username,
    validate_password,
    verify_password_hash,
    with_auth_transaction,
)
from apeiria.db.models.auth import WebUIAccount as WebUIAccountModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class WebUIAccount:
    """Stored Web UI account."""

    user_id: str
    username: str
    password_hash: str
    is_disabled: bool = False
    last_login_at: str | None = None
    password_changed_at: str | None = None
    session_version: int = 0


async def _user_items() -> list[dict[str, Any]]:
    data = await load_store_data_readonly()
    return data.users


def _build_account(item: dict[str, Any]) -> WebUIAccount | None:
    try:
        return WebUIAccount(
            user_id=str(item["user_id"]),
            username=str(item["username"]),
            password_hash=str(item["password_hash"]),
            is_disabled=bool(item.get("is_disabled", False)),
            last_login_at=(
                str(item.get("last_login_at"))
                if item.get("last_login_at") is not None
                else None
            ),
            password_changed_at=(
                str(item.get("password_changed_at"))
                if item.get("password_changed_at") is not None
                else None
            ),
            session_version=int(item.get("session_version") or 0),
        )
    except KeyError:
        return None


async def list_accounts() -> list[WebUIAccount]:
    """List all stored Web UI accounts."""
    accounts: list[WebUIAccount] = []
    for item in await _user_items():
        account = _build_account(item)
        if account is not None:
            accounts.append(account)
    return accounts


async def get_account_by_username(username: str) -> WebUIAccount | None:
    """Look up an account by normalized username."""
    normalized = normalize_username(username)
    all_accounts = await list_accounts()
    return next(
        (account for account in all_accounts if account.username == normalized),
        None,
    )


async def get_account_by_id(user_id: str) -> WebUIAccount | None:
    """Look up an account by user identifier."""
    return next(
        (account for account in await list_accounts() if account.user_id == user_id),
        None,
    )


async def create_account(username: str, password: str) -> str:
    """Create one account from the management surface."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)
    if await get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    password_hash = hash_password(password)

    async def _op(session: "AsyncSession") -> None:
        await _create_account_in_session(
            session,
            username=normalized_username,
            password_hash=password_hash,
        )

    await with_auth_transaction(_op)
    return normalized_username


async def verify_account_password(username: str, password: str) -> WebUIAccount | None:
    """Verify credentials and return the matching account when valid."""
    account = await get_account_by_username(username)
    if account is None or account.is_disabled:
        return None
    if not verify_password_hash(password, account.password_hash):
        return None
    return account


async def update_account_password(user_id: str, password: str) -> WebUIAccount | None:
    """Update one account password."""
    validate_password(password)

    async def _op(session: "AsyncSession") -> WebUIAccount | None:
        return await _update_account_password_in_session(session, user_id, password)

    return await with_auth_transaction(_op)


async def reset_account_password(user_id: str, password: str) -> WebUIAccount | None:
    """Reset one account password and enable the account."""
    validate_password(password)

    async def _op(session: "AsyncSession") -> WebUIAccount | None:
        return await _reset_account_password_in_session(session, user_id, password)

    return await with_auth_transaction(_op)


async def set_account_password(username: str, password: str) -> str:
    """Reset one account password from the host-side management surface."""
    normalized_username = normalize_username(username)
    validate_password(password)
    account = await get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")

    updated = await reset_account_password(account.user_id, password)
    if updated is None:
        raise ValueError("account_not_found")
    return normalized_username


async def set_account_disabled(
    user_id: str,
    *,
    disabled: bool,
    actor_user_id: str | None = None,
) -> WebUIAccount | None:
    """Enable or disable one account."""

    async def _op(session: "AsyncSession") -> WebUIAccount | None:
        return await _set_account_disabled_in_session(
            session,
            user_id,
            disabled=disabled,
            actor_user_id=actor_user_id,
        )

    return await with_auth_transaction(_op)


async def delete_account(
    user_id: str,
    *,
    actor_user_id: str | None = None,
) -> bool:
    """Delete one account."""

    async def _op(session: "AsyncSession") -> bool:
        return await _delete_account_in_session(
            session,
            user_id,
            actor_user_id=actor_user_id,
        )

    return bool(await with_auth_transaction(_op))


async def rotate_account_session_version(
    user_id: str,
) -> WebUIAccount | None:
    """Invalidate previous sessions for one account and return the updated record."""

    async def _op(session: "AsyncSession") -> WebUIAccount | None:
        return await _rotate_account_session_version_in_session(session, user_id)

    return await with_auth_transaction(_op)


async def record_login_success(user_id: str) -> WebUIAccount | None:
    """Update last-login metadata for one account."""

    async def _op(session: "AsyncSession") -> WebUIAccount | None:
        return await _record_login_success_in_session(session, user_id)

    return await with_auth_transaction(_op)


async def recover_owner_account(username: str, password: str) -> tuple[str, bool]:
    """Create or recover one account from the host."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)

    async def _op(session: "AsyncSession") -> tuple[str, bool]:
        return await _recover_account_in_session(session, normalized_username, password)

    return await with_auth_transaction(_op)


def _row_to_account(item: dict[str, Any]) -> WebUIAccount | None:
    return _build_account(item)


async def _load_account_by_user_id(
    session: "AsyncSession",
    user_id: str,
) -> WebUIAccount | None:
    return next(
        (
            account
            for item in await list_user_items(session)
            if str(item.get("user_id")) == user_id
            if (account := _row_to_account(item)) is not None
        ),
        None,
    )


async def _load_account_by_username(
    session: "AsyncSession",
    username: str,
) -> WebUIAccount | None:
    normalized = normalize_username(username)
    return next(
        (
            account
            for item in await list_user_items(session)
            if str(item.get("username") or "") == normalized
            if (account := _row_to_account(item)) is not None
        ),
        None,
    )


async def _enabled_account_count(session: "AsyncSession") -> int:
    return count_enabled_accounts(await list_user_items(session))


async def _create_account_in_session(
    session: "AsyncSession",
    *,
    username: str,
    password_hash: str,
) -> None:
    timestamp = iso_now()
    row = WebUIAccountModel(
        user_id=f"webui_{secrets.token_hex(8)}",
        username=username,
        password_hash=password_hash,
        is_disabled=0,
        last_login_at=None,
        password_changed_at=timestamp,  # type: ignore[arg-type]
        session_version=0,
        created_at=timestamp,  # type: ignore[arg-type]
        updated_at=timestamp,  # type: ignore[arg-type]
    )
    session.add(row)


async def _update_account_password_in_session(
    session: "AsyncSession",
    user_id: str,
    password: str,
) -> WebUIAccount | None:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    await session.execute(
        update(WebUIAccountModel)
        .where(WebUIAccountModel.user_id == user_id)
        .values(
            password_hash=hash_password(password),
            password_changed_at=timestamp,
            session_version=WebUIAccountModel.session_version + 1,
            updated_at=timestamp,
        )
    )
    await session.flush()
    return await _load_account_by_user_id(session, user_id)


async def _reset_account_password_in_session(
    session: "AsyncSession",
    user_id: str,
    password: str,
) -> WebUIAccount | None:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    await session.execute(
        update(WebUIAccountModel)
        .where(WebUIAccountModel.user_id == user_id)
        .values(
            password_hash=hash_password(password),
            password_changed_at=timestamp,
            session_version=WebUIAccountModel.session_version + 1,
            is_disabled=0,
            updated_at=timestamp,
        )
    )
    await session.flush()
    return await _load_account_by_user_id(session, user_id)


async def _set_account_disabled_in_session(
    session: "AsyncSession",
    user_id: str,
    *,
    disabled: bool,
    actor_user_id: str | None,
) -> WebUIAccount | None:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return None
    if actor_user_id and account.user_id == actor_user_id:
        raise ValueError("self_disable_forbidden")
    enabled_count = await _enabled_account_count(session)
    if disabled and not account.is_disabled and enabled_count <= 1:
        raise ValueError("last_account_forbidden")
    result = await session.execute(
        update(WebUIAccountModel)
        .where(WebUIAccountModel.user_id == user_id)
        .values(
            is_disabled=1 if disabled else 0,
            session_version=WebUIAccountModel.session_version + 1,
            updated_at=iso_now(),
        )
    )
    if not result.rowcount:
        return None
    await session.flush()
    return await _load_account_by_user_id(session, user_id)


async def _delete_account_in_session(
    session: "AsyncSession",
    user_id: str,
    *,
    actor_user_id: str | None,
) -> bool:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return False
    if actor_user_id and account.user_id == actor_user_id:
        raise ValueError("self_delete_forbidden")
    if not account.is_disabled and await _enabled_account_count(session) <= 1:
        raise ValueError("last_account_forbidden")
    result = await session.execute(
        delete(WebUIAccountModel).where(WebUIAccountModel.user_id == user_id)
    )
    return bool(result.rowcount)


async def _rotate_account_session_version_in_session(
    session: "AsyncSession",
    user_id: str,
) -> WebUIAccount | None:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return None
    await session.execute(
        update(WebUIAccountModel)
        .where(WebUIAccountModel.user_id == user_id)
        .values(
            session_version=WebUIAccountModel.session_version + 1,
            updated_at=iso_now(),
        )
    )
    await session.flush()
    return await _load_account_by_user_id(session, user_id)


async def _record_login_success_in_session(
    session: "AsyncSession",
    user_id: str,
) -> WebUIAccount | None:
    account = await _load_account_by_user_id(session, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    await session.execute(
        update(WebUIAccountModel)
        .where(WebUIAccountModel.user_id == user_id)
        .values(
            last_login_at=timestamp,
            updated_at=timestamp,
        )
    )
    await session.flush()
    return await _load_account_by_user_id(session, user_id)


async def _recover_account_in_session(
    session: "AsyncSession",
    normalized_username: str,
    password: str,
) -> tuple[str, bool]:
    account = await _load_account_by_username(session, normalized_username)
    timestamp = iso_now()
    if account is not None:
        await session.execute(
            update(WebUIAccountModel)
            .where(WebUIAccountModel.user_id == account.user_id)
            .values(
                password_hash=hash_password(password),
                password_changed_at=timestamp,
                session_version=WebUIAccountModel.session_version + 1,
                is_disabled=0,
                updated_at=timestamp,
            )
        )
        return normalized_username, False

    row = WebUIAccountModel(
        user_id=f"webui_{secrets.token_hex(8)}",
        username=normalized_username,
        password_hash=hash_password(password),
        is_disabled=0,
        last_login_at=None,
        password_changed_at=timestamp,  # type: ignore[arg-type]
        session_version=0,
        created_at=timestamp,  # type: ignore[arg-type]
        updated_at=timestamp,  # type: ignore[arg-type]
    )
    session.add(row)
    return normalized_username, True


__all__ = [
    "WebUIAccount",
    "create_account",
    "delete_account",
    "get_account_by_id",
    "get_account_by_username",
    "list_accounts",
    "record_login_success",
    "recover_owner_account",
    "reset_account_password",
    "rotate_account_session_version",
    "set_account_disabled",
    "set_account_password",
    "update_account_password",
    "verify_account_password",
]
