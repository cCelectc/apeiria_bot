"""Web UI session lifecycle — database-backed session management."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from apeiria.config.webui_config import get_web_ui_config
from apeiria.db.engine import get_session
from apeiria.db.models.auth import WebUISession as WebUISessionModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SESSION_ID_BYTES = 32


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


class SessionNotFoundError(Exception):
    """Session identifier does not match any active session record."""


class SessionExpiredError(Exception):
    """Session has passed its absolute expiry time."""


class SessionRevokedError(Exception):
    """Session has been explicitly revoked."""


@dataclass(frozen=True)
class WebUISessionRecord:
    user_id: str
    expires_at: str
    last_active_at: str


async def create_session(user_id: str, *, ttl_days: int | None = None) -> str:
    if ttl_days is None:
        ttl_days = get_web_ui_config().session_ttl_days

    session_id = secrets.token_urlsafe(_SESSION_ID_BYTES)
    now = _now_iso()
    expires_at = (_now_dt() + timedelta(days=ttl_days)).isoformat()

    async with get_session() as db:
        row = WebUISessionModel(
            id=session_id,
            user_id=int(user_id),
            expires_at=expires_at,
            last_active_at=now,
            created_at=now,
        )
        db.add(row)
        await db.commit()

    return session_id


async def verify_session(session_id: str) -> WebUISessionRecord:
    async with get_session() as db:
        row = await _load_session(db, session_id)
        now = _now_iso()

        if row is None:
            raise SessionNotFoundError
        if row.revoked:
            raise SessionRevokedError
        if row.expires_at < now:
            raise SessionExpiredError

        await db.execute(
            update(WebUISessionModel)
            .where(WebUISessionModel.id == session_id)
            .values(last_active_at=now)
        )
        await db.commit()

        return WebUISessionRecord(
            user_id=str(row.user_id),
            expires_at=row.expires_at,
            last_active_at=now,
        )


async def revoke_session(session_id: str) -> None:
    async with get_session() as db:
        await db.execute(
            update(WebUISessionModel)
            .where(WebUISessionModel.id == session_id)
            .values(revoked=1)
        )
        await db.commit()


async def revoke_user_sessions(
    user_id: str,
    *,
    except_session_id: str | None = None,
) -> None:
    async with get_session() as db:
        stmt = update(WebUISessionModel).where(
            WebUISessionModel.user_id == int(user_id),
            WebUISessionModel.revoked == 0,
        )
        if except_session_id:
            stmt = stmt.where(WebUISessionModel.id != except_session_id)
        stmt = stmt.values(revoked=1)
        await db.execute(stmt)
        await db.commit()


async def cleanup_expired_sessions() -> int:
    now = _now_iso()
    async with get_session() as db:
        result = await db.execute(
            delete(WebUISessionModel).where(
                WebUISessionModel.expires_at < now,
                WebUISessionModel.revoked == 1,
            )
        )
        await db.commit()
        return result.rowcount or 0


async def _load_session(
    db: "AsyncSession",
    session_id: str,
) -> WebUISessionModel | None:
    result = await db.execute(
        select(WebUISessionModel).where(WebUISessionModel.id == session_id)
    )
    return result.scalar_one_or_none()
