from __future__ import annotations

from sqlalchemy import select, update

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session
from apeiria.db.models.conversation import Message, Session


async def ensure_session(
    session_id: str,
    platform: str,
    scene_type: str,
    scene_id: str,
) -> Session:
    async with get_session() as db:
        existing = (
            await db.execute(select(Session).where(Session.id == session_id))
        ).scalar_one_or_none()
        if existing:
            existing.last_active_at = _now_iso()
            await db.commit()
            return existing
        new_session = Session(
            id=session_id,
            platform=platform,
            scene_type=scene_type,
            scene_id=scene_id,
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session


async def append_message(  # noqa: PLR0913
    session_id: str,
    role: str,
    content: str,
    *,
    user_id: str | None = None,
    message_id: str | None = None,
    msg_type: str = "message",
    meta_json: str | None = None,
) -> Message:
    async with get_session() as db:
        msg = Message(
            session_id=session_id,
            role=role,
            type=msg_type,
            content=content,
            user_id=user_id,
            message_id=message_id,
            meta_json=meta_json,
        )
        db.add(msg)
        session = (
            await db.execute(select(Session).where(Session.id == session_id))
        ).scalar_one_or_none()
        if session:
            session.last_active_at = _now_iso()
        await db.commit()
        await db.refresh(msg)
        return msg


async def load_recent(
    session_id: str,
    limit: int = 99,
) -> list[Message]:
    async with get_session() as db:
        session = (
            await db.execute(select(Session).where(Session.id == session_id))
        ).scalar_one_or_none()
        if not session:
            return []

        query = select(Message).where(Message.session_id == session_id)

        if session.last_compacted_message_id is not None:
            system_msgs = (
                (
                    await db.execute(
                        query.where(
                            Message.role == "system",
                            Message.id <= session.last_compacted_message_id,
                        ).order_by(Message.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )

            recent_msgs = (
                (
                    await db.execute(
                        query.where(
                            Message.id > session.last_compacted_message_id,
                        )
                        .order_by(Message.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )

            return list(system_msgs) + list(reversed(recent_msgs))

        rows = (
            (await db.execute(query.order_by(Message.created_at.desc()).limit(limit)))
            .scalars()
            .all()
        )
        return list(reversed(rows))


async def get_session_by_id(session_id: str) -> Session | None:
    async with get_session() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()


async def update_session_model_override(
    session_id: str,
    model_override: str | None,
) -> None:
    async with get_session() as db:
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(model_override=model_override)
        )
        await db.commit()


async def update_session_compaction(
    session_id: str,
    last_compacted_message_id: int | None,
) -> None:
    async with get_session() as db:
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                last_compacted_message_id=last_compacted_message_id,
                last_active_at=_now_iso(),
            )
        )
        await db.commit()


async def search_messages_by_keyword(
    session_id: str,
    keyword: str,
    *,
    limit: int = 20,
) -> list[Message]:
    async with get_session() as db:
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.content.contains(keyword),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
