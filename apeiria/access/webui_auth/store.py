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
from apeiria.i18n import t
from apeiria.utils.files import atomic_write_text

_PASSWORD_HASH_N = 2**14
_PASSWORD_HASH_R = 8
_PASSWORD_HASH_P = 1
_PASSWORD_HASH_LEN = 64
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128

if TYPE_CHECKING:
    from pathlib import Path


def _apply_secret_permissions(secret_file: "Path") -> None:
    with contextlib.suppress(OSError):
        secret_file.chmod(0o600)


def _get_secret_file() -> "Path":
    from nonebot_plugin_localstore import get_data_file

    return get_data_file("web_ui", "secret.json")


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
        "username": normalize_username(str(item.get("username") or "")),
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
            "created_at": iso_now(),
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
        "created_at": str(item.get("created_at") or iso_now()),
        "created_by": str(item.get("created_by") or "unknown"),
    }


def load_or_create_raw() -> dict[str, Any]:
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
            persist_raw(upgraded)
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
    persist_raw(data)
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
                new_registration_code(role=ROLE_OWNER, created_by="system")
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
                "password_hash": hash_password(legacy_password),
                "role": ROLE_OWNER,
                "is_disabled": False,
            }
        )
    return _ensure_bootstrap_registration_code(upgraded)


def persist_raw(data: dict[str, Any]) -> None:
    """Persist auth storage to disk."""
    secret_file = _get_secret_file()
    atomic_write_text(
        secret_file,
        json.dumps(data, ensure_ascii=True, indent=2),
    )
    _apply_secret_permissions(secret_file)


class LazyAuthStore(dict[str, Any]):
    """Lazy-loading auth store to avoid requiring NoneBot during import."""

    def __init__(self) -> None:
        super().__init__()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        super().update(load_or_create_raw())
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
