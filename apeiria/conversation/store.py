from __future__ import annotations

from sqlalchemy import delete, select

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_db
from apeiria.db.models.conversation import Message, Session


async def ensure_session(
    session_id: str,
    platform: str,
    scene_type: str,
    scene_id: str,
) -> Session:
    db = get_db()
    now = _now_iso()
    async with db.gate.write() as sess:
        existing = (
            await sess.execute(select(Session).where(Session.session_id == session_id))
        ).scalar_one_or_none()
        if existing:
            existing.updated_at = now
            return existing
        new_session = Session(
            session_id=session_id,
            platform=platform,
            scene_type=scene_type,
            scene_id=scene_id,
        )
        sess.add(new_session)
        await sess.flush()
        return new_session


async def append_message(  # noqa: PLR0913
    session_id: str,
    role: str,
    content: str,
    *,
    user_id: str | None = None,
    message_id: str | None = None,
    meta_json: dict | None = None,
) -> Message | None:
    db = get_db()
    now = _now_iso()
    async with db.gate.write() as sess:
        session = (
            await sess.execute(select(Session).where(Session.session_id == session_id))
        ).scalar_one_or_none()
        if session is None:
            from nonebot.log import logger

            logger.warning(
                "append_message: session not found, skipping: {}", session_id
            )
            return None

        msg = Message(
            session_id=session.id,
            role=role,
            content=content,
            user_id=user_id,
            message_id=message_id,
            time=now,
            meta_json=meta_json,
        )
        sess.add(msg)
        session.updated_at = now
        await sess.flush()
        return msg


async def load_recent(
    session_id: str,
    limit: int = 20,
) -> list[Message]:
    db = get_db()
    async with db.gate.read() as sess:
        session = (
            await sess.execute(select(Session).where(Session.session_id == session_id))
        ).scalar_one_or_none()
        if session is None:
            return []
        result = await sess.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def search_messages(
    session_id: str,
    keyword: str,
    limit: int = 10,
) -> list[Message]:
    db = get_db()
    async with db.gate.read() as sess:
        session = (
            await sess.execute(select(Session).where(Session.session_id == session_id))
        ).scalar_one_or_none()
        if session is None:
            return []
        result = await sess.execute(
            select(Message)
            .where(
                Message.session_id == session.id,
                Message.content.contains(keyword),
            )
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def delete_session_messages(session_id: str) -> int:
    """删除某会话的全部消息（保留 session 行），返回删除条数。"""
    db = get_db()
    async with db.gate.write() as sess:
        session = (
            await sess.execute(select(Session).where(Session.session_id == session_id))
        ).scalar_one_or_none()
        if session is None:
            return 0
        result = await sess.execute(
            delete(Message).where(Message.session_id == session.id)
        )
        return result.rowcount or 0  # pyright: ignore[reportAttributeAccessIssue]


async def delete_message(message_id: str) -> int:
    """按 message_id 删除单条消息，返回删除条数。"""
    db = get_db()
    async with db.gate.write() as sess:
        result = await sess.execute(
            delete(Message).where(Message.message_id == message_id)
        )
        return result.rowcount or 0  # pyright: ignore[reportAttributeAccessIssue]
