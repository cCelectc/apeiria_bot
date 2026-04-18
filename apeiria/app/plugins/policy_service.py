"""Plugin governance policy helpers."""

from __future__ import annotations

from apeiria.app.access.models import PluginPolicy
from apeiria.app.governance import audit_service
from apeiria.app.plugins.repository import plugin_catalog_repository
from apeiria.infra.runtime.plugin_policy import (
    get_default_protection_mode,
    get_plugin_kind,
)


class PluginPolicyService:
    """Read framework-owned governance policy for plugins."""

    def get_kind(self, module_name: str) -> str:
        return get_plugin_kind(module_name)

    async def get_policy(self, module_name: str) -> PluginPolicy:
        policy = await plugin_catalog_repository.get_plugin_policy(module_name)
        if policy is None:
            return PluginPolicy(
                plugin_module=module_name,
                access_mode="default_allow",
                required_level=0,
                protection_mode=get_default_protection_mode(module_name),  # type: ignore[arg-type]
            )
        return PluginPolicy(
            plugin_module=module_name,
            access_mode=policy.access_mode,  # type: ignore[arg-type]
            required_level=policy.required_level,
            protection_mode=policy.protection_mode,  # type: ignore[arg-type]
        )

    async def is_globally_enabled(self, module_name: str) -> bool:
        if get_default_protection_mode(module_name) == "required":
            return True
        return await plugin_catalog_repository.get_plugin_enabled(module_name)

    async def ensure_defaults(
        self,
        module_name: str,
        *,
        access_mode: str = "default_allow",
        required_level: int = 0,
    ) -> None:
        await plugin_catalog_repository.ensure_plugin_policy(
            module_name,
            access_mode=access_mode,
            required_level=required_level,
            protection_mode=get_default_protection_mode(module_name),
        )

    async def update_access_mode(
        self,
        module_name: str,
        *,
        access_mode: str,
    ) -> PluginPolicy:
        await plugin_catalog_repository.update_plugin_policy(
            module_name,
            access_mode=access_mode,
        )
        audit_service.record(
            "plugin.policy_update",
            target_kind="plugin",
            target_id=module_name,
            detail=f"access_mode={access_mode}",
            metadata={"access_mode": access_mode},
        )
        return await self.get_policy(module_name)


plugin_policy_service = PluginPolicyService()
