"""Low-level persistent Web UI auth storage primitives (SQLAlchemy async)."""

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
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.auth import WebUIAccount as WebUIAccountModel
from apeiria.db.models.auth import WebUIAuthSecret as WebUIAuthSecretModel
from apeiria.i18n import t
from apeiria.utils.project_context import current_project_root

_PASSWORD_HASH_N = 2**14
_PASSWORD_HASH_R = 8
_PASSWORD_HASH_P = 1
_PASSWORD_HASH_LEN = 64
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class WebUIAuthStoreData:
    token_secret: str
    users: list[dict[str, Any]]


def _apply_secret_permissions(secret_file: "Path") -> None:
    with contextlib.suppress(OSError):
        secret_file.chmod(0o600)


def _get_secret_file() -> "Path":
    return current_project_root() / "data" / "web_ui" / "secret.json"


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


def count_enabled_accounts(users: list[dict[str, Any]]) -> int:
    """Count enabled accounts in the current auth store."""
    return len(users)


async def load_store_data() -> WebUIAuthStoreData:
    """Load auth storage from SQLite, importing legacy JSON once when present."""
    imported_secret_file: Path | None = None
    async with get_session() as session:
        imported_secret_file = await _import_legacy_json_if_needed(session)
        data = await _load_store_data_from_session(session)
        if not data.token_secret:
            token_secret = secrets.token_urlsafe(32)
            timestamp = iso_now()
            row = WebUIAuthSecretModel(
                id=1,
                token_secret=token_secret,
                created_at=timestamp,  # type: ignore[arg-type]
            )
            await session.merge(row)
            logger.info("{}", t("web_ui.secrets.generated"))
        await session.commit()
    if imported_secret_file is not None:
        _backup_legacy_secret_file(imported_secret_file)
    return await load_store_data_readonly()


async def load_store_data_readonly() -> WebUIAuthStoreData:
    """Load auth storage from SQLite without mutating on read."""
    async with get_session() as session:
        return await _load_store_data_from_session(session)


async def with_auth_transaction(
    operation: "Callable[[AsyncSession], Awaitable[Any]]",
) -> Any:
    """Run one auth mutation within an async session transaction."""
    imported_secret_file: Path | None = None
    async with get_session() as session:
        imported_secret_file = await _import_legacy_json_if_needed(session)
        await _ensure_token_secret(session)
        result = await operation(session)
        await session.commit()
    if imported_secret_file is not None:
        _backup_legacy_secret_file(imported_secret_file)
    return result


async def get_token_secret() -> str:
    """Return the JWT signing secret."""
    data = await load_store_data()
    return data.token_secret


def get_secret_file_path() -> "Path":
    """Return the legacy auth storage file path when present."""
    return _get_secret_file()


async def list_user_items(session: "AsyncSession") -> list[dict[str, Any]]:
    return await _load_user_items(session)


async def _ensure_token_secret(session: "AsyncSession") -> str:
    token_secret = await _read_token_secret(session)
    if token_secret:
        return token_secret
    token_secret = secrets.token_urlsafe(32)
    timestamp = iso_now()
    row = WebUIAuthSecretModel(
        id=1,
        token_secret=token_secret,
        created_at=timestamp,  # type: ignore[arg-type]
    )
    await session.merge(row)
    return token_secret


async def _load_store_data_from_session(
    session: "AsyncSession",
) -> WebUIAuthStoreData:
    return WebUIAuthStoreData(
        token_secret=await _read_token_secret(session),
        users=await _load_user_items(session),
    )


async def _read_token_secret(session: "AsyncSession") -> str:
    result = await session.execute(
        select(WebUIAuthSecretModel.token_secret).where(WebUIAuthSecretModel.id == 1)
    )
    value = result.scalar_one_or_none()
    return str(value) if value is not None else ""


async def _load_user_items(session: "AsyncSession") -> list[dict[str, Any]]:
    result = await session.execute(
        select(WebUIAccountModel).order_by(WebUIAccountModel.username)
    )
    rows = result.scalars().all()
    return [
        {
            "user_id": str(row.id),
            "username": str(row.username),
            "password_hash": str(row.password_hash),
            "password_changed_at": (
                str(row.password_changed_at)
                if row.password_changed_at is not None
                else None
            ),
        }
        for row in rows
    ]


async def _replace_user_items(
    session: "AsyncSession",
    users: list[dict[str, Any]],
) -> None:
    from sqlalchemy import delete

    await session.execute(delete(WebUIAccountModel))
    for item in users:
        timestamp = iso_now()
        pwd_changed = item.get("password_changed_at")
        row = WebUIAccountModel(
            username=normalize_username(str(item["username"])),
            password_hash=str(item["password_hash"]),
            password_changed_at=str(pwd_changed) if pwd_changed is not None else None,  # type: ignore[arg-type]
            created_at=timestamp,  # type: ignore[arg-type]
            updated_at=timestamp,  # type: ignore[arg-type]
        )
        session.add(row)


async def _import_legacy_json_if_needed(session: "AsyncSession") -> "Path | None":
    secret_file = _get_secret_file()
    if not secret_file.is_file():
        return None
    if await _has_sqlite_auth_state(session):
        return None

    data = _load_legacy_json(secret_file)
    timestamp = iso_now()
    raw_secret = str(data.get("token_secret") or "").strip()
    token_secret = raw_secret or secrets.token_urlsafe(32)
    row = WebUIAuthSecretModel(
        id=1,
        token_secret=token_secret,
        created_at=timestamp,  # type: ignore[arg-type]
    )
    await session.merge(row)
    await _replace_user_items(
        session,
        [
            item
            for item in data.get("users", [])
            if isinstance(item, dict)
            and item.get("user_id")
            and item.get("username")
            and item.get("password_hash")
        ],
    )
    return secret_file


async def _has_sqlite_auth_state(session: "AsyncSession") -> bool:
    result = await session.execute(
        select(WebUIAuthSecretModel.token_secret).where(WebUIAuthSecretModel.id == 1)
    )
    value = result.scalar_one_or_none()
    if value is not None and bool(str(value).strip()):
        return True
    result = await session.execute(select(WebUIAccountModel.id).limit(1))
    return result.scalar_one_or_none() is not None


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


def _is_current_schema(data: dict[str, Any]) -> bool:
    return isinstance(data.get("users"), list)


def _is_legacy_schema(data: dict[str, Any]) -> bool:
    if "password" in data or "invite_codes" in data:
        return True
    if isinstance(data.get("registration_codes"), list):
        return True
    return isinstance(data.get("audit_events"), list)


def _backup_legacy_secret_file(secret_file: "Path") -> None:
    backup_file = secret_file.with_name(f"{secret_file.name}.v1.backup")
    counter = 1
    while backup_file.exists():
        backup_file = secret_file.with_name(f"{secret_file.name}.v1.backup.{counter}")
        counter += 1
    secret_file.replace(backup_file)
    _apply_secret_permissions(backup_file)


__all__ = [
    "WebUIAuthStoreData",
    "count_enabled_accounts",
    "get_secret_file_path",
    "get_token_secret",
    "hash_password",
    "iso_now",
    "list_user_items",
    "load_store_data",
    "load_store_data_readonly",
    "normalize_username",
    "validate_password",
    "verify_password_hash",
    "with_auth_transaction",
]
