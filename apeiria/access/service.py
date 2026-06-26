"""Access domain service — rules, groups, and runtime permission helpers."""

from __future__ import annotations

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.sqlite import insert

from apeiria.access.models import AccessContext, AccessPolicyRule
from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.governance import AccessRule, GroupState
from apeiria.utils.group_state import decode_disabled_plugins


class AccessService:
    """Runtime access persistence and group-state queries."""

    async def list_access_rules(self) -> list[AccessPolicyRule]:
        async with get_session() as db:
            rows = (await db.execute(select(AccessRule))).scalars().all()
        return [
            AccessPolicyRule(
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
        async with get_session() as db:
            await db.execute(stmt)
            await db.commit()

    async def delete_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        async with get_session() as db:
            result = await db.execute(
                delete(AccessRule).where(
                    AccessRule.subject_type == subject_type,
                    AccessRule.subject_id == subject_id,
                    AccessRule.plugin_name == plugin_module,
                )
            )
            await db.commit()
            return rowcount(result) > 0

    async def get_group_bot_enabled(self, group_id: str) -> bool:
        async with get_session() as db:
            result = await db.execute(
                select(GroupState.bot_enabled).where(
                    GroupState.group_id == group_id,
                )
            )
            row = result.scalar_one_or_none()
        return row is None or bool(row)

    async def get_group_disabled_plugins(self, group_id: str) -> list[str]:
        async with get_session() as db:
            result = await db.execute(
                select(GroupState.disabled_plugins_json).where(
                    GroupState.group_id == group_id,
                )
            )
            raw = result.scalar_one_or_none()
        return decode_disabled_plugins(raw)

    async def is_group_plugin_enabled(
        self,
        group_id: str,
        plugin_module: str,
    ) -> bool:
        disabled = await self.get_group_disabled_plugins(group_id)
        return plugin_module not in disabled

    async def get_explicit_rules(
        self,
        *,
        plugin_module: str,
        user_id: str,
        group_id: str | None = None,
    ) -> list[AccessPolicyRule]:
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
        async with get_session() as db:
            result = await db.execute(
                select(AccessRule).where(
                    AccessRule.plugin_name == plugin_module,
                    or_(*conditions),
                )
            )
            rows = result.scalars().all()
        return [
            AccessPolicyRule(
                subject_type=r.subject_type,
                subject_id=r.subject_id,
                plugin_module=r.plugin_name,
                effect=r.effect,
                note=r.note,
            )
            for r in rows
        ]

    async def get_explicit_rule(
        self,
        context: "AccessContext",
        plugin_module: str,
    ) -> "AccessPolicyRule | None":
        from apeiria.access.policy import resolve_explicit_rule

        rules = await self.get_explicit_rules(
            user_id=context.user_id,
            group_id=context.group_id,
            plugin_module=plugin_module,
        )
        return resolve_explicit_rule(context, plugin_module, rules)


access_service = AccessService()
