"""Persistence helpers for access-related state."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.governance import AccessRule, GroupState
from apeiria.utils.group_state import decode_disabled_plugins


@dataclass(frozen=True)
class AccessRuleRow:
    """Persisted explicit access rule."""

    subject_type: str
    subject_id: str
    plugin_module: str
    effect: str
    note: str | None = None


class AccessRepository:
    """Own access persistence via SQLAlchemy async session."""

    async def get_group_bot_enabled(self, group_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(GroupState.bot_enabled).where(GroupState.group_id == group_id)
            )
            row = result.scalar_one_or_none()
        return row is None or bool(row)

    async def get_group_disabled_plugins(self, group_id: str) -> list[str]:
        async with get_session() as session:
            result = await session.execute(
                select(GroupState.disabled_plugins_json).where(
                    GroupState.group_id == group_id
                )
            )
            raw = result.scalar_one_or_none()
        return decode_disabled_plugins(raw)

    async def list_access_rules(self) -> list[AccessRuleRow]:
        async with get_session() as session:
            result = await session.execute(
                select(AccessRule).order_by(
                    AccessRule.subject_type,
                    AccessRule.subject_id,
                    AccessRule.plugin_name,
                )
            )
            rows = result.scalars().all()
        return [
            AccessRuleRow(
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                plugin_module=r.plugin_name,
                effect=r.effect,
                note=r.note,
            )
            for r in rows
        ]

    async def get_explicit_rules_for_subjects(
        self,
        *,
        plugin_module: str,
        user_id: str,
        group_id: str | None,
    ) -> list[AccessRuleRow]:
        from sqlalchemy import and_, or_

        conditions = [
            and_(
                AccessRule.subject_type == "user",
                AccessRule.subject_id == user_id,
            )
        ]
        if group_id is not None:
            conditions.append(
                and_(
                    AccessRule.subject_type == "group",
                    AccessRule.subject_id == group_id,
                )
            )
        async with get_session() as session:
            result = await session.execute(
                select(AccessRule).where(
                    AccessRule.plugin_name == plugin_module,
                    or_(*conditions),
                )
            )
            rows = result.scalars().all()
        return [
            AccessRuleRow(
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                plugin_module=r.plugin_name,
                effect=r.effect,
                note=r.note,
            )
            for r in rows
        ]

    async def upsert_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
        effect: str,
        note: str | None = None,
    ) -> None:
        now = _now_iso()
        stmt = insert(AccessRule).values(
            subject_type=subject_type,
            subject_id=subject_id,
            plugin_name=plugin_module,
            effect=effect,
            note=note,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                AccessRule.subject_type,
                AccessRule.subject_id,
                AccessRule.plugin_name,
            ],
            set_={
                "effect": stmt.excluded.effect,
                "note": stmt.excluded.note,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()

    async def delete_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(AccessRule).where(
                    AccessRule.subject_type == subject_type,
                    AccessRule.subject_id == subject_id,
                    AccessRule.plugin_name == plugin_module,
                )
            )
            await session.commit()
        return rowcount(result) > 0


access_repository = AccessRepository()
