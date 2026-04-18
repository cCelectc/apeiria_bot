"""Persistent Web UI authentication storage."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.shared.files import atomic_write_text
from apeiria.shared.i18n import t
from apeiria.shared.principal_roles import (
    ROLE_OWNER,
    normalize_supported_role,
)

_PASSWORD_HASH_N = 2**14
_PASSWORD_HASH_R = 8
_PASSWORD_HASH_P = 1
_PASSWORD_HASH_LEN = 64
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128

if TYPE_CHECKING:
    from pathlib import Path


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


@dataclass(frozen=True)
class WebUISecurityAuditEvent:
    """Stored security audit event."""

    event_type: str
    occurred_at: str
    actor_username: str | None = None
    target_username: str | None = None
    detail: str | None = None


def _apply_secret_permissions(secret_file: "Path") -> None:
    with contextlib.suppress(OSError):
        secret_file.chmod(0o600)


def _get_secret_file() -> "Path":
    from nonebot_plugin_localstore import get_data_file

    return get_data_file("web_ui", "secret.json")


def _hash_password(password: str, *, salt: str | None = None) -> str:
    """Hash a password with scrypt and return an encoded storage string."""
    actual_salt = salt or secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt.encode("utf-8"),
        n=_PASSWORD_HASH_N,
        r=_PASSWORD_HASH_R,
        p=_PASSWORD_HASH_P,
        dklen=_PASSWORD_HASH_LEN,
    )
    return f"scrypt${actual_salt}${derived.hex()}"


def _verify_password_hash(password: str, encoded: str) -> bool:
    """Validate a plaintext password against the stored scrypt hash."""
    algorithm, _, payload = encoded.partition("$")
    if algorithm != "scrypt" or "$" not in payload:
        return False
    salt, _, _expected = payload.partition("$")
    actual = _hash_password(password, salt=salt)
    return hmac.compare_digest(actual, encoded)


def _normalize_username(username: str) -> str:
    """Normalize usernames for storage and comparison."""
    return username.strip().lower()


def _validate_password(password: str) -> None:
    """Validate password length before hashing."""

    if not (_PASSWORD_MIN_LENGTH <= len(password) <= _PASSWORD_MAX_LENGTH):
        raise ValueError("password_invalid")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_registration_code(*, role: str, created_by: str) -> dict[str, str]:
    return {
        "code": secrets.token_urlsafe(32),
        "role": normalize_supported_role(role, fallback=ROLE_OWNER),
        "created_at": _iso_now(),
        "created_by": created_by,
    }


def _record_audit_event(
    event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    current_events = [
        item for item in _auth_store.get("audit_events", []) if isinstance(item, dict)
    ]
    current_events.append(
        {
            "event_type": event_type,
            "occurred_at": _iso_now(),
            "actor_username": actor_username,
            "target_username": target_username,
            "detail": detail,
        }
    )
    _auth_store["audit_events"] = current_events[-100:]
    _mirror_to_governance_audit(
        event_type,
        actor_username=actor_username,
        target_username=target_username,
        detail=detail,
    )


def _mirror_to_governance_audit(
    event_type: str,
    *,
    actor_username: str | None,
    target_username: str | None,
    detail: str | None,
) -> None:
    """Forward webui audit events into the unified governance audit stream."""

    try:
        from apeiria.app.governance import AuditActor, audit_service
    except Exception:  # noqa: BLE001
        return
    kind = f"auth.{event_type}"
    allowed = {
        "auth.login_succeeded",
        "auth.login_failed",
        "auth.password_changed",
        "auth.sessions_revoked",
        "auth.account_created",
        "auth.account_disabled",
        "auth.account_enabled",
        "auth.account_deleted",
        "auth.registration_code_created",
        "auth.registration_code_revoked",
        "auth.registration_code_used",
        "auth.owner_account_recovered",
    }
    if kind not in allowed:
        return
    actor = (
        AuditActor(
            actor_kind="webui_account" if actor_username != "host" else "host_operator",
            actor_id=actor_username,
            display_name=actor_username,
        )
        if actor_username
        else None
    )
    try:
        audit_service.record(
            kind,  # type: ignore[arg-type]
            actor=actor,
            target_kind="webui_account" if target_username else None,
            target_id=target_username,
            detail=detail,
        )
    except Exception:  # noqa: BLE001
        return


def _enabled_owner_count() -> int:
    """Count enabled owner accounts in the current auth store."""

    return sum(
        1
        for item in _auth_store.get("users", [])
        if isinstance(item, dict)
        if normalize_supported_role(item.get("role"), fallback=ROLE_OWNER) == ROLE_OWNER
        if not bool(item.get("is_disabled", False))
    )


def _ensure_supported_role(role: object) -> str:
    """Normalize a role and reject unsupported values."""

    normalized_role = normalize_supported_role(role)
    if not normalized_role:
        raise ValueError("invalid_role")
    return normalized_role


def _ensure_bootstrap_registration_code(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure there is one bootstrap registration code when auth is fully empty."""
    users = [item for item in data.get("users", []) if isinstance(item, dict)]
    registration_codes = [
        item for item in data.get("registration_codes", []) if isinstance(item, dict)
    ]
    if users or registration_codes:
        return data
    data["registration_codes"] = [
        _new_registration_code(role=ROLE_OWNER, created_by="system")
    ]
    return data


def _normalize_user_item(item: object, *, index: int) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None

    role = normalize_supported_role(
        item.get("role"),
        fallback=ROLE_OWNER if index == 0 else "",
    )

    generated_user_id = f"webui_{secrets.token_hex(8)}"
    return {
        "user_id": str(item.get("user_id") or generated_user_id),
        "username": _normalize_username(str(item.get("username") or "")),
        "password_hash": str(item.get("password_hash") or ""),
        "role": role,
        "is_disabled": bool(item.get("is_disabled", False)),
        "last_login_at": (
            str(item.get("last_login_at"))
            if item.get("last_login_at") is not None
            else None
        ),
        "password_changed_at": (
            str(item.get("password_changed_at"))
            if item.get("password_changed_at") is not None
            else None
        ),
        "session_version": int(item.get("session_version") or 0),
    }


def _normalize_registration_code_item(item: object) -> dict[str, str] | None:
    if isinstance(item, str):
        return {
            "code": item.strip(),
            "role": ROLE_OWNER,
            "created_at": _iso_now(),
            "created_by": "legacy",
        }

    if not isinstance(item, dict):
        return None

    code = str(item.get("code") or "").strip()
    if not code:
        return None

    return {
        "code": code,
        "role": normalize_supported_role(item.get("role"), fallback=ROLE_OWNER),
        "created_at": str(item.get("created_at") or _iso_now()),
        "created_by": str(item.get("created_by") or "unknown"),
    }


def _load_or_create_raw() -> dict[str, Any]:
    """Load raw auth storage from disk, creating a default document when missing."""
    secret_file = _get_secret_file()
    if secret_file.is_file():
        try:
            data = json.loads(secret_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.opt(exception=exc).critical(
                "Web UI auth storage is corrupted: {}",
                secret_file,
            )
            msg = (
                "web_ui auth storage is corrupted; "
                "fix or restore secret.json before startup"
            )
            raise RuntimeError(msg) from exc
        except OSError as exc:
            logger.opt(exception=exc).critical(
                "Failed to read Web UI auth storage: {}",
                secret_file,
            )
            msg = "web_ui auth storage is unreadable"
            raise RuntimeError(msg) from exc

        if isinstance(data, dict) and "token_secret" in data:
            upgraded = _upgrade_legacy_schema(data)
            _persist_raw(upgraded)
            return upgraded

        logger.critical("Web UI auth storage has unsupported schema: {}", secret_file)
        msg = "web_ui auth storage has unsupported schema"
        raise RuntimeError(msg)

    data = {
        "token_secret": secrets.token_urlsafe(32),
        "users": [],
        "registration_codes": [],
        "audit_events": [],
    }
    data = _ensure_bootstrap_registration_code(data)
    _persist_raw(data)
    logger.info("{}", t("web_ui.secrets.generated"))
    return data


def _upgrade_legacy_schema(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy single-password storage into the current account schema."""
    users = data.get("users")
    registration_codes = data.get("registration_codes")
    if not isinstance(registration_codes, list):
        registration_codes = data.get("invite_codes")
    if isinstance(users, list) and isinstance(registration_codes, list):
        normalized_users = [
            normalized
            for index, item in enumerate(users)
            if (normalized := _normalize_user_item(item, index=index)) is not None
        ]
        normalized_registration_codes = [
            normalized
            for item in registration_codes
            if (normalized := _normalize_registration_code_item(item)) is not None
        ]

        if not normalized_users and not normalized_registration_codes:
            normalized_registration_codes = [
                _new_registration_code(role=ROLE_OWNER, created_by="system")
            ]

        return _ensure_bootstrap_registration_code(
            {
                "token_secret": str(data["token_secret"]),
                "users": normalized_users,
                "registration_codes": normalized_registration_codes,
                "audit_events": [
                    item
                    for item in data.get("audit_events", [])
                    if isinstance(item, dict)
                ],
            }
        )

    upgraded = {
        "token_secret": str(data["token_secret"]),
        "users": [],
        "registration_codes": [],
        "audit_events": [],
    }
    legacy_password = data.get("password")
    if isinstance(legacy_password, str) and legacy_password:
        upgraded["users"].append(
            {
                "user_id": "webui_admin",
                "username": "admin",
                "password_hash": _hash_password(legacy_password),
                "role": ROLE_OWNER,
                "is_disabled": False,
            }
        )
    return _ensure_bootstrap_registration_code(upgraded)


def _persist_raw(data: dict[str, Any]) -> None:
    """Persist auth storage to disk."""
    secret_file = _get_secret_file()
    atomic_write_text(
        secret_file,
        json.dumps(data, ensure_ascii=True, indent=2),
    )
    _apply_secret_permissions(secret_file)


class _LazyAuthStore(dict[str, Any]):
    """Lazy-loading auth store to avoid requiring NoneBot during import."""

    def __init__(self) -> None:
        super().__init__()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        super().update(_load_or_create_raw())
        self._loaded = True

    def __getitem__(self, key: str) -> Any:
        self._ensure_loaded()
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._ensure_loaded()
        super().__setitem__(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return super().get(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return super().pop(key, default)


_auth_store = _LazyAuthStore()


def get_token_secret() -> str:
    """Return the JWT signing secret."""
    return str(_auth_store["token_secret"])


def get_secret_file_path() -> "Path":
    """Return the auth storage file path."""
    return _get_secret_file()


def list_accounts() -> list[WebUIAccount]:
    """List all stored Web UI accounts."""
    accounts: list[WebUIAccount] = []
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        try:
            role = normalize_supported_role(item.get("role"))
            if not role:
                continue
            accounts.append(
                WebUIAccount(
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
            )
        except KeyError:
            continue
    return accounts


def get_account_by_username(username: str) -> WebUIAccount | None:
    """Look up an account by normalized username."""
    normalized = _normalize_username(username)
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

    normalized_username = _normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    _validate_password(password)
    normalized_role = _ensure_supported_role(role)
    if get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    _auth_store["users"] = [
        *[item for item in _auth_store.get("users", []) if isinstance(item, dict)],
        {
            "user_id": f"webui_{secrets.token_hex(8)}",
            "username": normalized_username,
            "password_hash": _hash_password(password),
            "role": normalized_role,
            "is_disabled": False,
            "password_changed_at": _iso_now(),
            "session_version": 0,
        },
    ]
    _record_audit_event(
        "account_created",
        actor_username="host",
        target_username=normalized_username,
    )
    _persist_raw(_auth_store)
    return normalized_username


def verify_account_password(username: str, password: str) -> WebUIAccount | None:
    """Verify credentials and return the matching account when valid."""
    account = get_account_by_username(username)
    if account is None:
        return None
    if account.is_disabled:
        return None
    if not _verify_password_hash(password, account.password_hash):
        return None
    return account


def list_registration_codes() -> list[WebUIRegistrationCode]:
    """List all registration codes."""
    registration_codes: list[WebUIRegistrationCode] = []
    for item in _auth_store.get(
        "registration_codes",
        _auth_store.get("invite_codes", []),
    ):
        if not isinstance(item, dict):
            continue
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


def list_security_audit_events(limit: int = 20) -> list[WebUISecurityAuditEvent]:
    """List recent security audit events."""
    items = [
        WebUISecurityAuditEvent(
            event_type=str(item.get("event_type") or "unknown"),
            occurred_at=str(item.get("occurred_at") or ""),
            actor_username=(
                str(item.get("actor_username"))
                if item.get("actor_username") is not None
                else None
            ),
            target_username=(
                str(item.get("target_username"))
                if item.get("target_username") is not None
                else None
            ),
            detail=str(item.get("detail")) if item.get("detail") is not None else None,
        )
        for item in _auth_store.get("audit_events", [])
        if isinstance(item, dict)
    ]
    return items[-limit:][::-1]


def record_security_audit_event(
    event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    """Persist one explicit audit event."""

    _record_audit_event(
        event_type,
        actor_username=actor_username,
        target_username=target_username,
        detail=detail,
    )
    _persist_raw(_auth_store)


def create_registration_code(
    *,
    role: str = ROLE_OWNER,
    created_by: str = "host",
) -> WebUIRegistrationCode:
    """Create and persist one registration code."""
    normalized_role = _ensure_supported_role(role)
    registration_code = _new_registration_code(
        role=normalized_role,
        created_by=created_by,
    )
    current_registration_codes = [
        item
        for item in _auth_store.get(
            "registration_codes",
            _auth_store.get("invite_codes", []),
        )
        if isinstance(item, dict)
    ]
    _auth_store["registration_codes"] = [
        *current_registration_codes,
        registration_code,
    ]
    _auth_store.pop("invite_codes", None)
    _record_audit_event(
        "registration_code_created",
        actor_username=created_by,
        detail=normalized_role,
    )
    _persist_raw(_auth_store)
    return WebUIRegistrationCode(**registration_code)


def revoke_registration_code(
    code: str,
    *,
    revoked_by: str | None = None,
) -> str:
    """Delete one registration code."""
    normalized = code.strip()
    current = [
        item
        for item in _auth_store.get(
            "registration_codes",
            _auth_store.get("invite_codes", []),
        )
        if isinstance(item, dict)
    ]
    next_registration_codes = [
        item for item in current if str(item.get("code") or "").strip() != normalized
    ]
    if len(next_registration_codes) == len(current):
        raise ValueError("registration_code_not_found")
    _auth_store["registration_codes"] = next_registration_codes
    _auth_store.pop("invite_codes", None)
    _record_audit_event(
        "registration_code_revoked",
        actor_username=revoked_by,
        detail=None,
    )
    _persist_raw(_auth_store)
    return normalized


def update_account_password(user_id: str, password: str) -> WebUIAccount | None:
    """Update one account password."""
    _validate_password(password)
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != user_id:
            continue
        item["password_hash"] = _hash_password(password)
        item["password_changed_at"] = _iso_now()
        item["session_version"] = int(item.get("session_version") or 0) + 1
        _record_audit_event(
            "password_changed",
            actor_username=str(item.get("username") or ""),
            target_username=str(item.get("username") or ""),
        )
        _persist_raw(_auth_store)
        return get_account_by_username(str(item.get("username") or ""))
    return None


def set_account_password(username: str, password: str) -> str:
    """Reset one account password from the host-side management surface."""

    normalized_username = _normalize_username(username)
    _validate_password(password)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != account.user_id:
            continue
        item["password_hash"] = _hash_password(password)
        item["password_changed_at"] = _iso_now()
        item["session_version"] = int(item.get("session_version") or 0) + 1
        item["is_disabled"] = False
        _record_audit_event(
            "password_changed",
            actor_username="host",
            target_username=normalized_username,
        )
        _persist_raw(_auth_store)
        return normalized_username
    raise ValueError("account_not_found")


def update_account_role(user_id: str, role: str) -> WebUIAccount | None:
    """Update one account role."""
    normalized_role = normalize_supported_role(role)
    if not normalized_role:
        return None
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != user_id:
            continue
        item["role"] = normalized_role
        _persist_raw(_auth_store)
        return get_account_by_username(str(item.get("username") or ""))
    return None


def set_account_disabled(username: str, *, disabled: bool) -> str:
    """Enable or disable one account from the host-side management surface."""

    normalized_username = _normalize_username(username)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")
    if (
        disabled
        and account.role == ROLE_OWNER
        and not account.is_disabled
        and _enabled_owner_count() <= 1
    ):
        raise ValueError("last_owner_forbidden")

    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != account.user_id:
            continue
        item["is_disabled"] = disabled
        item["session_version"] = int(item.get("session_version") or 0) + 1
        _record_audit_event(
            "account_disabled" if disabled else "account_enabled",
            actor_username="host",
            target_username=normalized_username,
        )
        _persist_raw(_auth_store)
        return normalized_username
    raise ValueError("account_not_found")


def delete_account(username: str) -> str:
    """Delete one account from the host-side management surface."""

    normalized_username = _normalize_username(username)
    account = get_account_by_username(normalized_username)
    if account is None:
        raise ValueError("account_not_found")
    if (
        account.role == ROLE_OWNER
        and not account.is_disabled
        and _enabled_owner_count() <= 1
    ):
        raise ValueError("last_owner_forbidden")

    _auth_store["users"] = [
        item
        for item in _auth_store.get("users", [])
        if isinstance(item, dict)
        if str(item.get("user_id")) != account.user_id
    ]
    _record_audit_event(
        "account_deleted",
        actor_username="host",
        target_username=normalized_username,
    )
    _persist_raw(_auth_store)
    return normalized_username


def rotate_account_session_version(
    user_id: str,
    *,
    actor_username: str,
) -> WebUIAccount | None:
    """Invalidate previous sessions for one account and return the updated record."""
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != user_id:
            continue
        item["session_version"] = int(item.get("session_version") or 0) + 1
        _record_audit_event(
            "sessions_revoked",
            actor_username=actor_username,
            target_username=str(item.get("username") or ""),
        )
        _persist_raw(_auth_store)
        return get_account_by_username(str(item.get("username") or ""))
    return None


def record_login_success(user_id: str) -> WebUIAccount | None:
    """Update last-login metadata for one account."""
    for item in _auth_store.get("users", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id")) != user_id:
            continue
        item["last_login_at"] = _iso_now()
        _record_audit_event(
            "login_succeeded",
            actor_username=str(item.get("username") or ""),
            target_username=str(item.get("username") or ""),
        )
        _persist_raw(_auth_store)
        return get_account_by_username(str(item.get("username") or ""))
    return None


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
            for item in _auth_store.get(
                "registration_codes",
                _auth_store.get("invite_codes", []),
            )
            if isinstance(item, dict)
            if str(item.get("code") or "").strip() == normalized_registration_code
        ),
        None,
    )
    if registration_code_item is None:
        raise ValueError("registration_code_invalid")

    normalized_username = _normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    _validate_password(password)
    if get_account_by_username(normalized_username) is not None:
        raise ValueError("username_taken")

    account = WebUIAccount(
        user_id=f"webui_{secrets.token_hex(8)}",
        username=normalized_username,
        password_hash=_hash_password(password),
        role=normalize_supported_role(
            registration_code_item.get("role"),
            fallback=ROLE_OWNER,
        ),
        is_disabled=False,
    )
    _auth_store["users"] = [
        *[item for item in _auth_store.get("users", []) if isinstance(item, dict)],
        {
            "user_id": account.user_id,
            "username": account.username,
            "password_hash": account.password_hash,
            "role": account.role,
            "is_disabled": account.is_disabled,
        },
    ]
    _auth_store["registration_codes"] = [
        item
        for item in _auth_store.get(
            "registration_codes",
            _auth_store.get("invite_codes", []),
        )
        if not (
            isinstance(item, dict)
            and str(item.get("code") or "").strip() == normalized_registration_code
        )
    ]
    _auth_store.pop("invite_codes", None)
    _record_audit_event(
        "registration_code_used",
        actor_username=normalized_username,
        target_username=normalized_username,
        detail=account.role,
    )
    _persist_raw(_auth_store)
    return account


def recover_owner_account(username: str, password: str) -> tuple[str, bool]:
    """Create or recover one owner account from the host."""

    normalized_username = _normalize_username(username)
    if not normalized_username:
        raise ValueError("username_invalid")
    _validate_password(password)

    account = get_account_by_username(normalized_username)
    if account is not None:
        for item in _auth_store.get("users", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("user_id")) != account.user_id:
                continue
            item["password_hash"] = _hash_password(password)
            item["password_changed_at"] = _iso_now()
            item["session_version"] = int(item.get("session_version") or 0) + 1
            item["role"] = ROLE_OWNER
            item["is_disabled"] = False
            _record_audit_event(
                "owner_account_recovered",
                actor_username="host",
                target_username=normalized_username,
            )
            _persist_raw(_auth_store)
            return normalized_username, False

    _auth_store["users"] = [
        *[item for item in _auth_store.get("users", []) if isinstance(item, dict)],
        {
            "user_id": f"webui_{secrets.token_hex(8)}",
            "username": normalized_username,
            "password_hash": _hash_password(password),
            "role": ROLE_OWNER,
            "is_disabled": False,
            "password_changed_at": _iso_now(),
            "session_version": 0,
        },
    ]
    _record_audit_event(
        "owner_account_recovered",
        actor_username="host",
        target_username=normalized_username,
    )
    _persist_raw(_auth_store)
    return normalized_username, True
