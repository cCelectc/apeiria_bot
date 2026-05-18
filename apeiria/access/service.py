"""Application-facing access service."""

from __future__ import annotations

from apeiria.access.context import build_access_context
from apeiria.access.models import AccessContext, AccessPolicyRule
from apeiria.access.policy import resolve_explicit_rule
from apeiria.access.repository import access_repository


class AccessService:
    """Facade for access context, group state, and explicit rules."""

    build_context = staticmethod(build_access_context)

    async def is_group_bot_enabled(self, group_id: str) -> bool:
        return await access_repository.get_group_bot_enabled(group_id)

    async def is_group_plugin_enabled(self, group_id: str, plugin_module: str) -> bool:
        disabled = await access_repository.get_group_disabled_plugins(group_id)
        return plugin_module not in disabled

    async def get_explicit_rule(
        self,
        context: AccessContext,
        plugin_module: str,
    ) -> AccessPolicyRule | None:
        rows = await access_repository.get_explicit_rules_for_subjects(
            plugin_module=plugin_module,
            user_id=context.user_id,
            group_id=context.group_id,
        )
        rules = [
            AccessPolicyRule(
                subject_type=row.subject_type,  # type: ignore[arg-type]
                subject_id=row.subject_id,
                plugin_module=row.plugin_module,
                effect=row.effect,  # type: ignore[arg-type]
                note=row.note,
            )
            for row in rows
        ]
        return resolve_explicit_rule(context, plugin_module, rules)

    async def list_access_rules(self) -> list[AccessPolicyRule]:
        rows = await access_repository.list_access_rules()
        return [
            AccessPolicyRule(
                subject_type=row.subject_type,  # type: ignore[arg-type]
                subject_id=row.subject_id,
                plugin_module=row.plugin_module,
                effect=row.effect,  # type: ignore[arg-type]
                note=row.note,
            )
            for row in rows
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
        await access_repository.upsert_access_rule(
            subject_type=subject_type,
            subject_id=subject_id,
            plugin_module=plugin_module,
            effect=effect,
            note=note,
        )

    async def delete_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
    ) -> bool:
        return await access_repository.delete_access_rule(
            subject_type=subject_type,
            subject_id=subject_id,
            plugin_module=plugin_module,
        )


access_service = AccessService()
