from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_write_gate_serializes() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from apeiria.db.base import Base
    from apeiria.db.engine import DbWriteGate
    from apeiria.db.models.access import AccessRule

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    gate = DbWriteGate(sm)
    results: list[int] = []

    async def writer(n: int) -> None:
        async with gate.write() as sess:
            rule = AccessRule(
                subject_type="user",
                subject_id=f"u{n}",
                action="allow",
                priority=0,
            )
            sess.add(rule)
            await asyncio.sleep(0.01)
            results.append(n)

    await asyncio.gather(writer(1), writer(2), writer(3))
    assert len(results) == 3


@pytest.mark.asyncio
async def test_access_rule_crud() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from apeiria.db.base import Base
    from apeiria.db.engine import DbWriteGate
    from apeiria.db.models.access import AccessRule

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    gate = DbWriteGate(sm)

    async with gate.write() as sess:
        rule = AccessRule(
            subject_type="group", subject_id="g1", action="deny", priority=10
        )
        sess.add(rule)
        await sess.flush()
        assert rule.id is not None

    async with gate.read() as sess:
        found = (
            await sess.execute(select(AccessRule).where(AccessRule.subject_id == "g1"))
        ).scalar_one()
        assert found.action == "deny"


@pytest.mark.asyncio
async def test_session_and_message() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from apeiria.db.base import Base
    from apeiria.db.engine import DbWriteGate
    from apeiria.db.models.conversation import Message, Session

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    gate = DbWriteGate(sm)

    async with gate.write() as sess:
        s = Session(
            session_id="qq:group:12345",
            platform="qq",
            scene_type="group",
            scene_id="12345",
        )
        sess.add(s)
        await sess.flush()
        msg = Message(
            session_id=s.id,
            role="user",
            content="hello",
            user_id="u1",
            time="2026-01-01T00:00:00",
        )
        sess.add(msg)
        await sess.flush()
        assert msg.id is not None
