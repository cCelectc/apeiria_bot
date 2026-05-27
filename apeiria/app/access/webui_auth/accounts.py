"""Web UI account lifecycle."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

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


def _user_items() -> list[dict[str, Any]]:
    return load_store_data_readonly().users


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


def list_accounts() -> list[WebUIAccount]:
    """List all stored Web UI accounts."""
    accounts: list[WebUIAccount] = []
    for item in _user_items():
        account = _build_account(item)
        if account is not None:
            accounts.append(account)
    return accounts


def get_account_by_username(username: str) -> WebUIAccount | None:
    """Look up an account by normalized username."""
    normalized = normalize_username(username)
    return next(
        (account for account in list_accounts() if account.username == normalized),
        None,
    )


def get_account_by_id(user_id: str) -> WebUIAccount | None:
    """Look up an account by user identifier."""
    return next(
        (account for account in list_accounts() if account.user_id == user_id),
        None,
    )


def create_account(username: str, password: str) -> str:
    """Create one account from the management surface."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)
    if get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    with_auth_transaction(
        lambda connection: _create_account_in_connection(
            connection,
            username=normalized_username,
            password_hash=hash_password(password),
        )
    )
    return normalized_username


def verify_account_password(username: str, password: str) -> WebUIAccount | None:
    """Verify credentials and return the matching account when valid."""
    account = get_account_by_username(username)
    if account is None or account.is_disabled:
        return None
    if not verify_password_hash(password, account.password_hash):
        return None
    return account


def update_account_password(user_id: str, password: str) -> WebUIAccount | None:
    """Update one account password."""
    validate_password(password)
    return with_auth_transaction(
        lambda connection: _update_account_password_in_connection(
            connection,
            user_id,
            password,
        )
    )


def reset_account_password(user_id: str, password: str) -> WebUIAccount | None:
    """Reset one account password and enable the account."""
    validate_password(password)
    return with_auth_transaction(
        lambda connection: _reset_account_password_in_connection(
            connection,
            user_id,
            password,
        )
    )


def set_account_password(username: str, password: str) -> str:
    """Reset one account password from the host-side management surface."""
    normalized_username = normalize_username(username)
    validate_password(password)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")

    updated = reset_account_password(account.user_id, password)
    if updated is None:
        raise ValueError("account_not_found")
    return normalized_username


def set_account_disabled(
    user_id: str,
    *,
    disabled: bool,
    actor_user_id: str | None = None,
) -> WebUIAccount | None:
    """Enable or disable one account."""
    return with_auth_transaction(
        lambda connection: _set_account_disabled_in_connection(
            connection,
            user_id,
            disabled=disabled,
            actor_user_id=actor_user_id,
        )
    )


def delete_account(
    user_id: str,
    *,
    actor_user_id: str | None = None,
) -> bool:
    """Delete one account."""
    return bool(
        with_auth_transaction(
            lambda connection: _delete_account_in_connection(
                connection,
                user_id,
                actor_user_id=actor_user_id,
            )
        )
    )


def rotate_account_session_version(
    user_id: str,
) -> WebUIAccount | None:
    """Invalidate previous sessions for one account and return the updated record."""
    return with_auth_transaction(
        lambda connection: _rotate_account_session_version_in_connection(
            connection,
            user_id,
        )
    )


def record_login_success(user_id: str) -> WebUIAccount | None:
    """Update last-login metadata for one account."""
    return with_auth_transaction(
        lambda connection: _record_login_success_in_connection(connection, user_id)
    )


def recover_owner_account(username: str, password: str) -> tuple[str, bool]:
    """Create or recover one account from the host."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)

    return with_auth_transaction(
        lambda connection: _recover_account_in_connection(
            connection,
            normalized_username,
            password,
        )
    )


def _row_to_account(item: dict[str, Any]) -> WebUIAccount | None:
    return _build_account(item)


def _load_account_by_user_id(
    connection: Any,
    user_id: str,
) -> WebUIAccount | None:
    return next(
        (
            account
            for item in list_user_items(connection)
            if str(item.get("user_id")) == user_id
            if (account := _row_to_account(item)) is not None
        ),
        None,
    )


def _load_account_by_username(
    connection: Any,
    username: str,
) -> WebUIAccount | None:
    normalized = normalize_username(username)
    return next(
        (
            account
            for item in list_user_items(connection)
            if str(item.get("username") or "") == normalized
            if (account := _row_to_account(item)) is not None
        ),
        None,
    )


def _enabled_account_count(connection: Any) -> int:
    return count_enabled_accounts(list_user_items(connection))


def _create_account_in_connection(
    connection: Any,
    *,
    username: str,
    password_hash: str,
) -> None:
    timestamp = iso_now()
    connection.execute(
        """
        INSERT INTO webui_account (
            user_id,
            username,
            password_hash,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, 0, NULL, ?, 0, ?, ?)
        """,
        (
            f"webui_{secrets.token_hex(8)}",
            username,
            password_hash,
            timestamp,
            timestamp,
            timestamp,
        ),
    )


def _update_account_password_in_connection(
    connection: Any,
    user_id: str,
    password: str,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    connection.execute(
        """
        UPDATE webui_account
        SET password_hash = ?,
            password_changed_at = ?,
            session_version = session_version + 1,
            updated_at = ?
        WHERE user_id = ?
        """,
        (hash_password(password), timestamp, timestamp, user_id),
    )
    return _load_account_by_user_id(connection, user_id)


def _reset_account_password_in_connection(
    connection: Any,
    user_id: str,
    password: str,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    connection.execute(
        """
        UPDATE webui_account
        SET password_hash = ?,
            password_changed_at = ?,
            session_version = session_version + 1,
            is_disabled = 0,
            updated_at = ?
        WHERE user_id = ?
        """,
        (hash_password(password), timestamp, timestamp, user_id),
    )
    return _load_account_by_user_id(connection, user_id)


def _set_account_disabled_in_connection(
    connection: Any,
    user_id: str,
    *,
    disabled: bool,
    actor_user_id: str | None,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    if actor_user_id and account.user_id == actor_user_id:
        raise ValueError("self_disable_forbidden")
    if disabled and not account.is_disabled and _enabled_account_count(connection) <= 1:
        raise ValueError("last_account_forbidden")
    updated = connection.execute(
        """
        UPDATE webui_account
        SET is_disabled = ?,
            session_version = session_version + 1,
            updated_at = ?
        WHERE user_id = ?
        """,
        (1 if disabled else 0, iso_now(), user_id),
    ).rowcount
    if not updated:
        return None
    return _load_account_by_user_id(connection, user_id)


def _delete_account_in_connection(
    connection: Any,
    user_id: str,
    *,
    actor_user_id: str | None,
) -> bool:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return False
    if actor_user_id and account.user_id == actor_user_id:
        raise ValueError("self_delete_forbidden")
    if not account.is_disabled and _enabled_account_count(connection) <= 1:
        raise ValueError("last_account_forbidden")
    deleted = connection.execute(
        """
        DELETE FROM webui_account
        WHERE user_id = ?
        """,
        (user_id,),
    ).rowcount
    return bool(deleted)


def _rotate_account_session_version_in_connection(
    connection: Any,
    user_id: str,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    connection.execute(
        """
        UPDATE webui_account
        SET session_version = session_version + 1,
            updated_at = ?
        WHERE user_id = ?
        """,
        (iso_now(), user_id),
    )
    return _load_account_by_user_id(connection, user_id)


def _record_login_success_in_connection(
    connection: Any,
    user_id: str,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    timestamp = iso_now()
    connection.execute(
        """
        UPDATE webui_account
        SET last_login_at = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (timestamp, timestamp, user_id),
    )
    return _load_account_by_user_id(connection, user_id)


def _recover_account_in_connection(
    connection: Any,
    normalized_username: str,
    password: str,
) -> tuple[str, bool]:
    account = _load_account_by_username(connection, normalized_username)
    timestamp = iso_now()
    if account is not None:
        connection.execute(
            """
            UPDATE webui_account
            SET password_hash = ?,
                password_changed_at = ?,
                session_version = session_version + 1,
                is_disabled = 0,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                hash_password(password),
                timestamp,
                timestamp,
                account.user_id,
            ),
        )
        return normalized_username, False

    connection.execute(
        """
        INSERT INTO webui_account (
            user_id,
            username,
            password_hash,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, 0, NULL, ?, 0, ?, ?)
        """,
        (
            f"webui_{secrets.token_hex(8)}",
            normalized_username,
            hash_password(password),
            timestamp,
            timestamp,
            timestamp,
        ),
    )
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
