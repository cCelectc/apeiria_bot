"""Application-owned access management workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.access.groups import group_service
from apeiria.access.service import access_service
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.plugins.catalog import plugin_governance_service
from apeiria.plugins.policy import plugin_policy_service

if TYPE_CHECKING:
    from apeiria.access.models import AccessPolicyRule
    from apeiria.plugins.models import PluginCatalogEntry


@dataclass(frozen=True, slots=True)
class PluginAccessSummary:
    access_mode: str
    user_allow_count: int
    user_deny_count: int
    group_allow_count: int
    group_deny_count: int
    disabled_group_count: int


class AccessManagementService:
    """Compose access and plugin governance for owner-facing management flows."""

    async def list_access_rules(self) -> list["AccessPolicyRule"]:
        return await access_service.list_access_rules()

    async def upsert_access_rule(
        self,
        *,
        subject_type: str,
        subject_id: str,
        plugin_module: str,
        effect: str,
        note: str | None = None,
    ) -> None:
        await self.get_manageable_plugin(plugin_module)
        await access_service.upsert_access_rule(
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
        return await access_service.delete_access_rule(
            subject_type=subject_type,
            subject_id=subject_id,
            plugin_module=plugin_module,
        )

    async def get_manageable_plugin(
        self,
        module_name: str,
    ) -> "PluginCatalogEntry":
        plugin = await plugin_governance_service.get_plugin(module_name)
        if plugin is None:
            raise ResourceNotFoundError(module_name)
        if plugin.governance_state.kind == "core":
            raise ProtectedPluginError(module_name)
        return plugin

    async def update_plugin_access_mode(
        self,
        module_name: str,
        *,
        access_mode: str,
    ) -> None:
        await self.get_manageable_plugin(module_name)
        await plugin_policy_service.update_access_mode(
            module_name,
            access_mode=access_mode,
        )

    async def get_plugin_access_summary(self, module_name: str) -> PluginAccessSummary:
        plugin = await plugin_governance_service.get_plugin(module_name)
        if plugin is None:
            raise ResourceNotFoundError(module_name)

        policy = await plugin_policy_service.get_policy(module_name)
        rules = [
            rule
            for rule in await access_service.list_access_rules()
            if rule.plugin_module == module_name
        ]
        groups = await group_service.list_groups()
        disabled_groups = [
            group for group in groups if module_name in group.disabled_plugins
        ]

        return PluginAccessSummary(
            access_mode=policy.access_mode,
            user_allow_count=sum(
                1
                for rule in rules
                if rule.subject_type == "user" and rule.effect == "allow"
            ),
            user_deny_count=sum(
                1
                for rule in rules
                if rule.subject_type == "user" and rule.effect == "deny"
            ),
            group_allow_count=sum(
                1
                for rule in rules
                if rule.subject_type == "group" and rule.effect == "allow"
            ),
            group_deny_count=sum(
                1
                for rule in rules
                if rule.subject_type == "group" and rule.effect == "deny"
            ),
            disabled_group_count=len(disabled_groups),
        )


access_management_service = AccessManagementService()

__all__ = [
    "AccessManagementService",
    "PluginAccessSummary",
    "access_management_service",
]
