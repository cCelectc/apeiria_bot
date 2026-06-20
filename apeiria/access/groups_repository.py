"""Persistence helpers for group settings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session
from apeiria.db.models.governance import GroupState


@dataclass(frozen=True)
class GroupStateRow:
    """Persisted per-group governance state."""

    group_id: str
    group_name: str | None = None
    bot_status: bool = True
    disabled_plugins: str = "[]"
    updated_at: str | None = None


class GroupRepository:
    """Own group-state persistence via SQLAlchemy async session."""

    async def get_group(self, group_id: str) -> GroupStateRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(GroupState).where(GroupState.group_id == group_id)
            )
            row = result.scalars().first()
        if row is None:
            return None
        return self._to_row(row)

    async def list_groups(self) -> list[GroupStateRow]:
        async with get_session() as session:
            result = await session.execute(
                select(GroupState).order_by(
                    GroupState.updated_at.desc(),
                    GroupState.group_id,
                )
            )
            rows = result.scalars().all()
        return [self._to_row(r) for r in rows]

    async def save_group(self, row: GroupStateRow) -> None:
        now = _now_iso()
        stmt = insert(GroupState).values(
            group_id=row.group_id,
            group_name=row.group_name,
            bot_enabled=1 if row.bot_status else 0,
            disabled_plugins_json=row.disabled_plugins,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[GroupState.group_id],
            set_={
                "group_name": stmt.excluded.group_name,
                "bot_enabled": stmt.excluded.bot_enabled,
                "disabled_plugins_json": stmt.excluded.disabled_plugins_json,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    def _to_row(model: GroupState) -> GroupStateRow:
        return GroupStateRow(
            group_id=model.group_id,
            group_name=model.group_name,
            bot_status=bool(model.bot_enabled),
            disabled_plugins=model.disabled_plugins_json,
            updated_at=str(model.updated_at) if model.updated_at else None,
        )


group_repository = GroupRepository()
