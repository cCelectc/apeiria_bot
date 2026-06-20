from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.governance import AccessRule, PluginState


async def check_access(
    subject_type: str,
    subject_id: str,
    plugin_name: str,
) -> bool:
    async with get_session() as db:
        rule = (
            await db.execute(
                select(AccessRule).where(
                    AccessRule.subject_type == subject_type,
                    AccessRule.subject_id == subject_id,
                    AccessRule.plugin_name == plugin_name,
                )
            )
        ).scalar_one_or_none()

        if rule:
            return rule.effect == "allow"

        plugin = (
            await db.execute(
                select(PluginState).where(PluginState.plugin_id == plugin_name)
            )
        ).scalar_one_or_none()

        if plugin:
            return plugin.access_mode == "default_allow"

        return True


@dataclass(frozen=True)
class AccessPolicyRule:
    subject_type: str
    subject_id: str
    plugin_module: str
    effect: str
    note: str | None = None


class AccessService:
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
        async with get_session() as db:
            existing = (
                await db.execute(
                    select(AccessRule).where(
                        AccessRule.subject_type == subject_type,
                        AccessRule.subject_id == subject_id,
                        AccessRule.plugin_name == plugin_module,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.effect = effect
                existing.note = note
            else:
                db.add(
                    AccessRule(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        plugin_name=plugin_module,
                        effect=effect,
                        note=note,
                    )
                )
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
                sa_delete(AccessRule).where(
                    AccessRule.subject_type == subject_type,
                    AccessRule.subject_id == subject_id,
                    AccessRule.plugin_name == plugin_module,
                )
            )
            await db.commit()
            return (result.rowcount or 0) > 0


access_service = AccessService()
