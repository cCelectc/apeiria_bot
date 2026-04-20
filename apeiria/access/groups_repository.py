"""Persistence helpers for group settings."""

from __future__ import annotations

from nonebot_plugin_orm import get_session
from sqlalchemy import select

from apeiria.db.models.group import GroupConsole


class GroupRepository:
    """Own ORM access for persisted group settings."""

    async def get_group(self, group_id: str) -> GroupConsole | None:
        async with get_session() as session:
            result = await session.execute(
                select(GroupConsole).where(GroupConsole.group_id == group_id)
            )
            return result.scalar_one_or_none()

    async def list_groups(self) -> list[GroupConsole]:
        async with get_session() as session:
            result = await session.execute(
                select(GroupConsole).order_by(
                    GroupConsole.updated_at.desc(),
                    GroupConsole.id.desc(),
                )
            )
            rows = result.scalars().all()
        return list(rows)

    async def save_group(self, row: GroupConsole) -> None:
        async with get_session() as session:
            session.add(row)
            await session.commit()


group_repository = GroupRepository()
