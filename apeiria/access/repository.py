"""Persistence helpers for access-related state."""

from __future__ import annotations

from nonebot_plugin_orm import get_session
from sqlalchemy import delete, select

from apeiria.db.models.access_policy import AccessPolicyEntry
from apeiria.db.models.group import GroupConsole
from apeiria.db.models.level import LevelUser
from apeiria.utils.group_state import decode_disabled_plugins


class AccessRepository:
    """Own ORM access for group status, levels, and access rules."""

    async def get_user_level(self, user_id: str, group_id: str) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(LevelUser.level).where(
                    LevelUser.user_id == user_id,
                    LevelUser.group_id == group_id,
                )
            )
            row = result.scalar_one_or_none()
        return row if row is not None else 0

    async def list_user_levels(self) -> list[tuple[str, str, int]]:
        async with get_session() as session:
            result = await session.execute(select(LevelUser))
            rows = result.scalars().all()
        return [(row.user_id, row.group_id, row.level) for row in rows]

    async def set_user_level(self, user_id: str, group_id: str, level: int) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(LevelUser).where(
                    LevelUser.user_id == user_id,
                    LevelUser.group_id == group_id,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                session.add(LevelUser(user_id=user_id, group_id=group_id, level=level))
            else:
                record.level = level
            await session.commit()

    async def get_group_bot_enabled(self, group_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(GroupConsole.bot_status).where(GroupConsole.group_id == group_id)
            )
            value = result.scalar_one_or_none()
        return value is not False

    async def get_group_disabled_plugins(self, group_id: str) -> list[str]:
        async with get_session() as session:
            result = await session.execute(
                select(GroupConsole.disabled_plugins).where(
                    GroupConsole.group_id == group_id
                )
            )
            raw = result.scalar_one_or_none()
        return decode_disabled_plugins(raw)

    async def list_access_rules(self) -> list[AccessPolicyEntry]:
        async with get_session() as session:
            result = await session.execute(select(AccessPolicyEntry))
            rows = result.scalars().all()
        return list(rows)

    async def get_explicit_rules_for_subjects(
        self,
        *,
        plugin_module: str,
        user_id: str,
        group_id: str | None,
    ) -> list[AccessPolicyEntry]:
        async with get_session() as session:
            conditions = [
                (
                    (AccessPolicyEntry.subject_type == "user")
                    & (AccessPolicyEntry.subject_id == user_id)
                )
            ]
            if group_id is not None:
                conditions.append(
                    (AccessPolicyEntry.subject_type == "group")
                    & (AccessPolicyEntry.subject_id == group_id)
                )
            subject_filter = (
                conditions[0] if len(conditions) == 1 else conditions[0] | conditions[1]
            )
            result = await session.execute(
                select(AccessPolicyEntry).where(
                    AccessPolicyEntry.plugin_module == plugin_module,
                    subject_filter,
                )
            )
            rows = result.scalars().all()
        return list(rows)

    async def upsert_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
        effect: str,
        note: str | None = None,
    ) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(AccessPolicyEntry).where(
                    AccessPolicyEntry.subject_type == subject_type,
                    AccessPolicyEntry.subject_id == subject_id,
                    AccessPolicyEntry.plugin_module == plugin_module,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                session.add(
                    AccessPolicyEntry(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        plugin_module=plugin_module,
                        effect=effect,
                        note=note,
                    )
                )
            else:
                record.effect = effect
                record.note = note
            await session.commit()

    async def delete_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        async with get_session() as session:
            existing = await session.execute(
                select(AccessPolicyEntry).where(
                    AccessPolicyEntry.subject_type == subject_type,
                    AccessPolicyEntry.subject_id == subject_id,
                    AccessPolicyEntry.plugin_module == plugin_module,
                )
            )
            record = existing.scalar_one_or_none()
            if record is None:
                return False
            await session.execute(
                delete(AccessPolicyEntry).where(
                    AccessPolicyEntry.subject_type == subject_type,
                    AccessPolicyEntry.subject_id == subject_id,
                    AccessPolicyEntry.plugin_module == plugin_module,
                )
            )
            await session.commit()
        return True


access_repository = AccessRepository()
