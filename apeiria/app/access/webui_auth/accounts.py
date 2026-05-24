"""Web UI account and registration code lifecycle."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from apeiria.access.principal_roles import ROLE_OWNER, normalize_supported_role
from apeiria.app.access.webui_auth.store import (
    append_audit_event,
    count_enabled_owner_accounts,
    ensure_supported_role,
    hash_password,
    iso_now,
    list_registration_code_items,
    list_user_items,
    load_store_data_readonly,
    new_registration_code,
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
    role: str = ROLE_OWNER
    is_disabled: bool = False
    last_login_at: str | None = None
    password_changed_at: str | None = None
    session_version: int = 0


@dataclass(frozen=True)
class WebUIRegistrationCode:
    """Stored registration code metadata."""

    code: str
    role: str
    created_at: str
    created_by: str


def _user_items() -> list[dict[str, Any]]:
    return load_store_data_readonly().users


def _registration_code_items() -> list[dict[str, Any]]:
    return load_store_data_readonly().registration_codes


def _build_account(item: dict[str, Any]) -> WebUIAccount | None:
    try:
        role = normalize_supported_role(item.get("role"))
        if not role:
            return None
        return WebUIAccount(
            user_id=str(item["user_id"]),
            username=str(item["username"]),
            password_hash=str(item["password_hash"]),
            role=role,
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


def create_account(username: str, password: str, *, role: str = ROLE_OWNER) -> str:
    """Create one account from the host-side management surface."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)
    normalized_role = ensure_supported_role(role)
    if get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    with_auth_transaction(
        lambda connection: _create_account_in_connection(
            connection,
            username=normalized_username,
            password_hash=hash_password(password),
            role=normalized_role,
            actor_username="host",
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


def list_registration_codes() -> list[WebUIRegistrationCode]:
    """List all registration codes."""
    registration_codes: list[WebUIRegistrationCode] = []
    for item in _registration_code_items():
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        registration_codes.append(
            WebUIRegistrationCode(
                code=code,
                role=normalize_supported_role(item.get("role"), fallback=ROLE_OWNER),
                created_at=str(item.get("created_at") or ""),
                created_by=str(item.get("created_by") or "unknown"),
            )
        )
    return registration_codes


def create_registration_code(
    *,
    role: str = ROLE_OWNER,
    created_by: str = "host",
) -> WebUIRegistrationCode:
    """Create and persist one registration code."""
    normalized_role = ensure_supported_role(role)
    registration_code = new_registration_code(
        role=normalized_role,
        created_by=created_by,
    )
    with_auth_transaction(
        lambda connection: _insert_registration_code_in_connection(
            connection,
            registration_code,
            actor_username=created_by,
            detail=normalized_role,
        )
    )
    return WebUIRegistrationCode(**registration_code)


def revoke_registration_code(
    code: str,
    *,
    revoked_by: str | None = None,
) -> str:
    """Delete one registration code."""
    normalized = code.strip()
    deleted = with_auth_transaction(
        lambda connection: _delete_registration_code_in_connection(
            connection,
            normalized,
            actor_username=revoked_by,
        )
    )
    if not deleted:
        raise ValueError("registration_code_not_found")
    return normalized


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


def set_account_password(username: str, password: str) -> str:
    """Reset one account password from the host-side management surface."""
    normalized_username = normalize_username(username)
    validate_password(password)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")

    updated = with_auth_transaction(
        lambda connection: _set_account_password_in_connection(
            connection,
            account.user_id,
            normalized_username,
            password,
        )
    )
    if updated is None:
        raise ValueError("account_not_found")
    return normalized_username


def update_account_role(user_id: str, role: str) -> WebUIAccount | None:
    """Update one account role."""
    normalized_role = normalize_supported_role(role)
    if not normalized_role:
        return None
    return with_auth_transaction(
        lambda connection: _update_account_role_in_connection(
            connection,
            user_id,
            normalized_role,
        )
    )


def set_account_disabled(username: str, *, disabled: bool) -> str:
    """Enable or disable one account from the host-side management surface."""
    normalized_username = normalize_username(username)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")
    if (
        disabled
        and account.role == ROLE_OWNER
        and not account.is_disabled
        and count_enabled_owner_accounts(_user_items()) <= 1
    ):
        raise ValueError("last_owner_forbidden")

    updated = with_auth_transaction(
        lambda connection: _set_account_disabled_in_connection(
            connection,
            account.user_id,
            normalized_username,
            disabled=disabled,
        )
    )
    if updated is None:
        raise ValueError("account_not_found")
    return normalized_username


def delete_account(username: str) -> str:
    """Delete one account from the host-side management surface."""
    normalized_username = normalize_username(username)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")
    if (
        account.role == ROLE_OWNER
        and not account.is_disabled
        and count_enabled_owner_accounts(_user_items()) <= 1
    ):
        raise ValueError("last_owner_forbidden")

    deleted = with_auth_transaction(
        lambda connection: _delete_account_in_connection(
            connection,
            account.user_id,
            normalized_username,
        )
    )
    if not deleted:
        raise ValueError("account_not_found")
    return normalized_username


def rotate_account_session_version(
    user_id: str,
    *,
    actor_username: str,
) -> WebUIAccount | None:
    """Invalidate previous sessions for one account and return the updated record."""
    return with_auth_transaction(
        lambda connection: _rotate_account_session_version_in_connection(
            connection,
            user_id,
            actor_username=actor_username,
        )
    )


def record_login_success(user_id: str) -> WebUIAccount | None:
    """Update last-login metadata for one account."""
    return with_auth_transaction(
        lambda connection: _record_login_success_in_connection(connection, user_id)
    )


def register_account(
    registration_code: str,
    username: str,
    password: str,
) -> WebUIAccount:
    """Create a new account by consuming one registration code."""
    normalized_registration_code = registration_code.strip()
    registration_code_item = next(
        (
            item
            for item in _registration_code_items()
            if str(item.get("code") or "").strip() == normalized_registration_code
        ),
        None,
    )
    if registration_code_item is None:
        raise ValueError("registration_code_invalid")

    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)
    if get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    return with_auth_transaction(
        lambda connection: _register_account_in_connection(
            connection,
            normalized_registration_code,
            normalized_username,
            password,
        )
    )


def recover_owner_account(username: str, password: str) -> tuple[str, bool]:
    """Create or recover one owner account from the host."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    validate_password(password)

    return with_auth_transaction(
        lambda connection: _recover_owner_account_in_connection(
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


def _create_account_in_connection(
    connection: Any,
    *,
    username: str,
    password_hash: str,
    role: str,
    actor_username: str,
) -> None:
    timestamp = iso_now()
    connection.execute(
        """
        INSERT INTO webui_account (
            user_id,
            username,
            password_hash,
            role,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, 0, NULL, ?, 0, ?, ?)
        """,
        (
            f"webui_{secrets.token_hex(8)}",
            username,
            password_hash,
            role,
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    append_audit_event(
        connection,
        "account_created",
        actor_username=actor_username,
        target_username=username,
    )


def _insert_registration_code_in_connection(
    connection: Any,
    registration_code: dict[str, str],
    *,
    actor_username: str,
    detail: str,
) -> None:
    connection.execute(
        """
        INSERT INTO webui_registration_code (code, role, created_at, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (
            registration_code["code"],
            registration_code["role"],
            registration_code["created_at"],
            registration_code["created_by"],
        ),
    )
    append_audit_event(
        connection,
        "registration_code_created",
        actor_username=actor_username,
        detail=detail,
    )


def _delete_registration_code_in_connection(
    connection: Any,
    code: str,
    *,
    actor_username: str | None,
) -> bool:
    deleted = connection.execute(
        """
        DELETE FROM webui_registration_code
        WHERE code = ?
        """,
        (code,),
    ).rowcount
    if not deleted:
        return False
    append_audit_event(
        connection,
        "registration_code_revoked",
        actor_username=actor_username,
    )
    return True


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
    append_audit_event(
        connection,
        "password_changed",
        actor_username=account.username,
        target_username=account.username,
    )
    return _load_account_by_user_id(connection, user_id)


def _set_account_password_in_connection(
    connection: Any,
    user_id: str,
    normalized_username: str,
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
    append_audit_event(
        connection,
        "password_changed",
        actor_username="host",
        target_username=normalized_username,
    )
    return _load_account_by_user_id(connection, user_id)


def _update_account_role_in_connection(
    connection: Any,
    user_id: str,
    role: str,
) -> WebUIAccount | None:
    updated = connection.execute(
        """
        UPDATE webui_account
        SET role = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (role, iso_now(), user_id),
    ).rowcount
    if not updated:
        return None
    return _load_account_by_user_id(connection, user_id)


def _set_account_disabled_in_connection(
    connection: Any,
    user_id: str,
    normalized_username: str,
    *,
    disabled: bool,
) -> WebUIAccount | None:
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
    append_audit_event(
        connection,
        "account_disabled" if disabled else "account_enabled",
        actor_username="host",
        target_username=normalized_username,
    )
    return _load_account_by_user_id(connection, user_id)


def _delete_account_in_connection(
    connection: Any,
    user_id: str,
    normalized_username: str,
) -> bool:
    deleted = connection.execute(
        """
        DELETE FROM webui_account
        WHERE user_id = ?
        """,
        (user_id,),
    ).rowcount
    if not deleted:
        return False
    append_audit_event(
        connection,
        "account_deleted",
        actor_username="host",
        target_username=normalized_username,
    )
    return True


def _rotate_account_session_version_in_connection(
    connection: Any,
    user_id: str,
    *,
    actor_username: str,
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
    append_audit_event(
        connection,
        "sessions_revoked",
        actor_username=actor_username,
        target_username=account.username,
    )
    return _load_account_by_user_id(connection, user_id)


def _record_login_success_in_connection(
    connection: Any,
    user_id: str,
) -> WebUIAccount | None:
    account = _load_account_by_user_id(connection, user_id)
    if account is None:
        return None
    connection.execute(
        """
        UPDATE webui_account
        SET last_login_at = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (iso_now(), iso_now(), user_id),
    )
    append_audit_event(
        connection,
        "login_succeeded",
        actor_username=account.username,
        target_username=account.username,
    )
    return _load_account_by_user_id(connection, user_id)


def _register_account_in_connection(
    connection: Any,
    registration_code: str,
    normalized_username: str,
    password: str,
) -> WebUIAccount:
    registration_code_item = next(
        (
            item
            for item in list_registration_code_items(connection)
            if str(item.get("code") or "").strip() == registration_code
        ),
        None,
    )
    if registration_code_item is None:
        raise ValueError("registration_code_invalid")
    if _load_account_by_username(connection, normalized_username) is not None:
        raise ValueError("username_taken")
    account = WebUIAccount(
        user_id=f"webui_{secrets.token_hex(8)}",
        username=normalized_username,
        password_hash=hash_password(password),
        role=normalize_supported_role(
            registration_code_item.get("role"),
            fallback=ROLE_OWNER,
        ),
        is_disabled=False,
    )
    timestamp = iso_now()
    connection.execute(
        """
        INSERT INTO webui_account (
            user_id,
            username,
            password_hash,
            role,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, 0, NULL, NULL, 0, ?, ?)
        """,
        (
            account.user_id,
            account.username,
            account.password_hash,
            account.role,
            timestamp,
            timestamp,
        ),
    )
    deleted = connection.execute(
        """
        DELETE FROM webui_registration_code
        WHERE code = ?
        """,
        (registration_code,),
    ).rowcount
    if not deleted:
        raise ValueError("registration_code_invalid")
    append_audit_event(
        connection,
        "registration_code_used",
        actor_username=normalized_username,
        target_username=normalized_username,
        detail=account.role,
    )
    created = _load_account_by_user_id(connection, account.user_id)
    if created is None:
        raise ValueError("registration_failed")
    return created


def _recover_owner_account_in_connection(
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
                role = ?,
                is_disabled = 0,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                hash_password(password),
                timestamp,
                ROLE_OWNER,
                timestamp,
                account.user_id,
            ),
        )
        append_audit_event(
            connection,
            "owner_account_recovered",
            actor_username="host",
            target_username=normalized_username,
        )
        return normalized_username, False

    connection.execute(
        """
        INSERT INTO webui_account (
            user_id,
            username,
            password_hash,
            role,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, 0, NULL, ?, 0, ?, ?)
        """,
        (
            f"webui_{secrets.token_hex(8)}",
            normalized_username,
            hash_password(password),
            ROLE_OWNER,
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    append_audit_event(
        connection,
        "owner_account_recovered",
        actor_username="host",
        target_username=normalized_username,
    )
    return normalized_username, True


__all__ = [
    "WebUIAccount",
    "WebUIRegistrationCode",
    "create_account",
    "create_registration_code",
    "delete_account",
    "get_account_by_id",
    "get_account_by_username",
    "list_accounts",
    "list_registration_codes",
    "record_login_success",
    "recover_owner_account",
    "register_account",
    "revoke_registration_code",
    "rotate_account_session_version",
    "set_account_disabled",
    "set_account_password",
    "update_account_password",
    "update_account_role",
    "verify_account_password",
]
