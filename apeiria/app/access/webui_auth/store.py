"""Low-level persistent Web UI auth storage primitives."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.access.principal_roles import ROLE_OWNER, normalize_supported_role
from apeiria.db.runtime import ApeiriaDatabase
from apeiria.i18n import t
from apeiria.utils.project_context import current_project_root

_PASSWORD_HASH_N = 2**14
_PASSWORD_HASH_R = 8
_PASSWORD_HASH_P = 1
_PASSWORD_HASH_LEN = 64
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128
_MAX_AUDIT_EVENTS = 100

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


def _apply_secret_permissions(secret_file: "Path") -> None:
    with contextlib.suppress(OSError):
        secret_file.chmod(0o600)


def _get_secret_file() -> "Path":
    return current_project_root() / "data" / "web_ui" / "secret.json"


def _database() -> ApeiriaDatabase:
    return ApeiriaDatabase(project_root=current_project_root())


def hash_password(password: str, *, salt: str | None = None) -> str:
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


def verify_password_hash(password: str, encoded: str) -> bool:
    """Validate a plaintext password against the stored scrypt hash."""
    algorithm, _, payload = encoded.partition("$")
    if algorithm != "scrypt" or "$" not in payload:
        return False
    salt, _, _expected = payload.partition("$")
    actual = hash_password(password, salt=salt)
    return hmac.compare_digest(actual, encoded)


def normalize_username(username: str) -> str:
    """Normalize usernames for storage and comparison."""
    return username.strip().lower()


def validate_password(password: str) -> None:
    """Validate password length before hashing."""
    if not (_PASSWORD_MIN_LENGTH <= len(password) <= _PASSWORD_MAX_LENGTH):
        raise ValueError("password_invalid")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_registration_code(*, role: str, created_by: str) -> dict[str, str]:
    return {
        "code": secrets.token_urlsafe(32),
        "role": normalize_supported_role(role, fallback=ROLE_OWNER),
        "created_at": iso_now(),
        "created_by": created_by,
    }


def count_enabled_owner_accounts(data: dict[str, Any]) -> int:
    """Count enabled owner accounts in the current auth store."""
    return sum(
        1
        for item in data.get("users", [])
        if isinstance(item, dict)
        if normalize_supported_role(item.get("role"), fallback=ROLE_OWNER) == ROLE_OWNER
        if not bool(item.get("is_disabled", False))
    )


def ensure_supported_role(role: object) -> str:
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
        new_registration_code(role=ROLE_OWNER, created_by="system")
    ]
    return data


def load_or_create_raw() -> dict[str, Any]:
    """Load auth storage from SQLite, importing legacy JSON once when present."""
    database = _database()
    database.ensure_ready()
    imported_secret_file: Path | None = None
    with database.transaction_sync() as connection:
        imported_secret_file = _import_legacy_json_if_needed(connection)
        data = _load_raw_from_connection(connection)
        if not data["token_secret"]:
            token_secret = secrets.token_urlsafe(32)
            timestamp = iso_now()
            connection.execute(
                """
                INSERT INTO webui_auth_secret (
                    id,
                    token_secret,
                    created_at,
                    updated_at
                ) VALUES (1, ?, ?, ?)
                """,
                (token_secret, timestamp, timestamp),
            )
            data["token_secret"] = token_secret
            data = _ensure_bootstrap_registration_code(data)
            _persist_raw_in_connection(connection, data)
            logger.info("{}", t("web_ui.secrets.generated"))
    if imported_secret_file is not None:
        _backup_legacy_secret_file(imported_secret_file)
    return data


def _is_current_schema(data: dict[str, Any]) -> bool:
    return (
        isinstance(data.get("users"), list)
        and isinstance(data.get("registration_codes"), list)
        and isinstance(data.get("audit_events"), list)
    )


def _is_legacy_schema(data: dict[str, Any]) -> bool:
    if "password" in data or "invite_codes" in data:
        return True
    registration_codes = data.get("registration_codes")
    return isinstance(registration_codes, list) and any(
        isinstance(item, str) for item in registration_codes
    )


def _load_raw_from_connection(connection: "sqlite3.Connection") -> dict[str, Any]:
    token_secret = _read_token_secret(connection)
    return {
        "token_secret": token_secret,
        "users": _load_user_items(connection),
        "registration_codes": _load_registration_code_items(connection),
        "audit_events": _load_audit_event_items(connection),
    }


def _read_token_secret(connection: "sqlite3.Connection") -> str:
    row = connection.execute(
        """
        SELECT token_secret
        FROM webui_auth_secret
        WHERE id = 1
        """
    ).fetchone()
    return str(row[0]) if row is not None else ""


def _load_user_items(connection: "sqlite3.Connection") -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            user_id,
            username,
            password_hash,
            role,
            is_disabled,
            last_login_at,
            password_changed_at,
            session_version
        FROM webui_account
        ORDER BY username
        """
    ).fetchall()
    return [
        {
            "user_id": str(row[0]),
            "username": str(row[1]),
            "password_hash": str(row[2]),
            "role": str(row[3]),
            "is_disabled": bool(row[4]),
            "last_login_at": str(row[5]) if row[5] is not None else None,
            "password_changed_at": str(row[6]) if row[6] is not None else None,
            "session_version": int(row[7] or 0),
        }
        for row in rows
    ]


def _load_registration_code_items(
    connection: "sqlite3.Connection",
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT code, role, created_at, created_by
        FROM webui_registration_code
        ORDER BY created_at
        """
    ).fetchall()
    return [
        {
            "code": str(row[0]),
            "role": str(row[1]),
            "created_at": str(row[2]),
            "created_by": str(row[3]),
        }
        for row in rows
    ]


def _load_audit_event_items(connection: "sqlite3.Connection") -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT event_type, occurred_at, actor_username, target_username, detail
        FROM webui_security_audit_event
        ORDER BY id
        """
    ).fetchall()
    return [
        {
            "event_type": str(row[0]),
            "occurred_at": str(row[1]),
            "actor_username": str(row[2]) if row[2] is not None else None,
            "target_username": str(row[3]) if row[3] is not None else None,
            "detail": str(row[4]) if row[4] is not None else None,
        }
        for row in rows
    ]


def _persist_raw_in_connection(
    connection: "sqlite3.Connection",
    data: dict[str, Any],
) -> None:
    token_secret = str(data.get("token_secret") or "").strip()
    if not token_secret:
        token_secret = secrets.token_urlsafe(32)
        data["token_secret"] = token_secret
    timestamp = iso_now()
    connection.execute(
        """
        INSERT INTO webui_auth_secret (id, token_secret, created_at, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            token_secret = excluded.token_secret,
            updated_at = excluded.updated_at
        """,
        (token_secret, timestamp, timestamp),
    )
    _replace_user_items(connection, data.get("users", []))
    _replace_registration_code_items(connection, data.get("registration_codes", []))
    _replace_audit_event_items(connection, data.get("audit_events", []))


def _replace_user_items(
    connection: "sqlite3.Connection",
    users: object,
) -> None:
    connection.execute("DELETE FROM webui_account")
    if not isinstance(users, list):
        return
    for item in users:
        if not isinstance(item, dict):
            continue
        try:
            user_id = str(item["user_id"])
            username = normalize_username(str(item["username"]))
            password_hash = str(item["password_hash"])
        except KeyError:
            continue
        if not user_id or not username or not password_hash:
            continue
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username,
                password_hash,
                normalize_supported_role(item.get("role"), fallback=ROLE_OWNER),
                1 if bool(item.get("is_disabled", False)) else 0,
                str(item.get("last_login_at"))
                if item.get("last_login_at") is not None
                else None,
                str(item.get("password_changed_at"))
                if item.get("password_changed_at") is not None
                else None,
                int(item.get("session_version") or 0),
                timestamp,
                timestamp,
            ),
        )


def _replace_registration_code_items(
    connection: "sqlite3.Connection",
    registration_codes: object,
) -> None:
    connection.execute("DELETE FROM webui_registration_code")
    if not isinstance(registration_codes, list):
        return
    for item in registration_codes:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        connection.execute(
            """
            INSERT INTO webui_registration_code (code, role, created_at, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (
                code,
                normalize_supported_role(item.get("role"), fallback=ROLE_OWNER),
                str(item.get("created_at") or iso_now()),
                str(item.get("created_by") or "unknown"),
            ),
        )


def _replace_audit_event_items(
    connection: "sqlite3.Connection",
    audit_events: object,
) -> None:
    connection.execute("DELETE FROM webui_security_audit_event")
    if not isinstance(audit_events, list):
        return
    recent_events = (
        audit_events[-_MAX_AUDIT_EVENTS:]
        if len(audit_events) > _MAX_AUDIT_EVENTS
        else audit_events
    )
    for item in recent_events:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("event_type") or "").strip()
        if not event_type:
            continue
        connection.execute(
            """
            INSERT INTO webui_security_audit_event (
                event_type,
                occurred_at,
                actor_username,
                target_username,
                detail
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_type,
                str(item.get("occurred_at") or iso_now()),
                str(item.get("actor_username"))
                if item.get("actor_username") is not None
                else None,
                str(item.get("target_username"))
                if item.get("target_username") is not None
                else None,
                str(item.get("detail")) if item.get("detail") is not None else None,
            ),
        )


def _import_legacy_json_if_needed(connection: "sqlite3.Connection") -> "Path | None":
    secret_file = _get_secret_file()
    if not secret_file.is_file():
        return None
    if _has_sqlite_auth_state(connection):
        return None

    data = _load_legacy_json(secret_file)
    _persist_raw_in_connection(connection, data)
    return secret_file


def _has_sqlite_auth_state(connection: "sqlite3.Connection") -> bool:
    existing_tables = _table_names(connection)
    for table_name in (
        "webui_auth_secret",
        "webui_account",
        "webui_registration_code",
        "webui_security_audit_event",
    ):
        if table_name not in existing_tables:
            continue
        row = connection.execute(
            f"""
            SELECT 1 FROM {table_name} LIMIT 1
            """
        ).fetchone()
        if row is not None:
            return True
    return False


def _table_names(connection: "sqlite3.Connection") -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _load_legacy_json(secret_file: "Path") -> dict[str, Any]:
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

    if not isinstance(data, dict) or "token_secret" not in data:
        logger.critical("Web UI auth storage has unsupported schema: {}", secret_file)
        msg = "web_ui auth storage has unsupported schema"
        raise RuntimeError(msg)
    if _is_legacy_schema(data):
        logger.critical(
            "Web UI auth storage uses a legacy schema: {}",
            secret_file,
        )
        msg = (
            "legacy Web UI auth storage is unsupported; migrate or "
            "recreate data/web_ui/secret.json before startup"
        )
        raise RuntimeError(msg)
    if not _is_current_schema(data):
        logger.critical("Web UI auth storage has unsupported schema: {}", secret_file)
        msg = "web_ui auth storage has unsupported schema"
        raise RuntimeError(msg)
    return data


def _backup_legacy_secret_file(secret_file: "Path") -> None:
    backup_file = secret_file.with_name(f"{secret_file.name}.v1.backup")
    counter = 1
    while backup_file.exists():
        backup_file = secret_file.with_name(f"{secret_file.name}.v1.backup.{counter}")
        counter += 1
    secret_file.replace(backup_file)
    _apply_secret_permissions(backup_file)


def persist_raw(data: dict[str, Any]) -> None:
    """Persist auth storage to SQLite."""
    database = _database()
    database.ensure_ready()
    with database.transaction_sync() as connection:
        _persist_raw_in_connection(connection, data)


class LazyAuthStore(dict[str, Any]):
    """Lazy-loading auth store to avoid requiring NoneBot during import."""

    def __init__(self) -> None:
        super().__init__()
        self._loaded = False
        self._loaded_path: Path | None = None

    def _ensure_loaded(self) -> None:
        secret_file = _get_secret_file()
        if self._loaded and self._loaded_path == secret_file:
            return
        super().clear()
        super().update(load_or_create_raw())
        self._loaded = True
        self._loaded_path = secret_file

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


auth_store = LazyAuthStore()


def get_token_secret() -> str:
    """Return the JWT signing secret."""
    return str(auth_store["token_secret"])


def get_secret_file_path() -> "Path":
    """Return the auth storage file path."""
    return _get_secret_file()


__all__ = [
    "LazyAuthStore",
    "auth_store",
    "count_enabled_owner_accounts",
    "ensure_supported_role",
    "get_secret_file_path",
    "get_token_secret",
    "hash_password",
    "iso_now",
    "new_registration_code",
    "normalize_username",
    "persist_raw",
    "validate_password",
    "verify_password_hash",
]
