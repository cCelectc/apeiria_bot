"""Application-owned plugin management workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.plugins.store.update_check import (
    plugin_update_check_service,
    supports_plugin_update_check,
)
from apeiria.plugins.catalog import plugin_governance_service
from apeiria.plugins.settings import config_mutation_service, config_query_service

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.app.plugins.store.update_check import PluginUpdateCheckResult
    from apeiria.plugins.models import PluginCatalogEntry
    from apeiria.plugins.readme import PluginReadme
    from apeiria.plugins.registry import (
        AdapterConfigState,
        DriverConfigState,
        PluginConfigState,
    )
    from apeiria.plugins.settings import (
        ConfigTextView,
        ConfigValidationReport,
        ConfigView,
    )
    from apeiria.plugins.settings_cleanup import OrphanPluginConfigItem
    from apeiria.plugins.toggle import PluginTogglePreview, PluginToggleResult
    from apeiria.plugins.uninstall import PluginUninstallResult


@dataclass(frozen=True, slots=True)
class PluginWorkspaceState:
    plugin: "PluginCatalogEntry"
    can_package_update: bool
    enable_preview: "PluginTogglePreview | None" = None
    disable_preview: "PluginTogglePreview | None" = None
    settings: "ConfigView | None" = None


class PluginManagementService:
    """Compose plugin governance and settings for owner-facing surfaces."""

    async def list_plugins(self) -> list["PluginCatalogEntry"]:
        return await plugin_governance_service.list_plugins()

    async def get_plugin(self, module_name: str) -> "PluginCatalogEntry | None":
        return await plugin_governance_service.get_plugin(module_name)

    async def get_plugin_readme(self, module_name: str) -> "PluginReadme":
        return await plugin_governance_service.get_plugin_readme(module_name)

    async def get_plugin_readme_asset_path(
        self,
        module_name: str,
        relative_path: str,
    ) -> "Path":
        return await plugin_governance_service.get_plugin_readme_asset_path(
            module_name,
            relative_path,
        )

    async def build_plugin_workspace(
        self,
        module_name: str,
    ) -> "PluginWorkspaceState | None":
        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        enable_preview = None
        disable_preview = None
        if plugin.governance_state.can_enable_disable:
            enable_preview = await self.preview_toggle_plugin(
                module_name,
                enabled=True,
            )
            disable_preview = await self.preview_toggle_plugin(
                module_name,
                enabled=False,
            )

        settings = None
        if plugin.governance_state.can_edit_config:
            settings = self.get_plugin_view(module_name)

        return PluginWorkspaceState(
            plugin=plugin,
            can_package_update=self.can_package_update(plugin),
            enable_preview=enable_preview,
            disable_preview=disable_preview,
            settings=settings,
        )

    def can_package_update(self, plugin: "PluginCatalogEntry") -> bool:
        installed_package = plugin.package_binding.installed_package
        return bool(
            plugin.governance_state.can_uninstall
            and installed_package
            and supports_plugin_update_check(installed_package)
        )

    async def check_plugin_updates(
        self,
        *,
        force_refresh: bool = False,
    ) -> list["PluginUpdateCheckResult"]:
        return await plugin_update_check_service.check_plugins(
            await self.list_plugins(),
            force_refresh=force_refresh,
        )

    async def set_plugin_enabled(self, module_name: str, *, enabled: bool) -> bool:
        return await plugin_governance_service.set_plugin_enabled(
            module_name,
            enabled=enabled,
        )

    async def apply_plugin_toggle(
        self,
        module_name: str,
        *,
        enabled: bool,
        cascade: bool = False,
    ) -> "PluginToggleResult":
        return await plugin_governance_service.apply_plugin_toggle(
            module_name,
            enabled=enabled,
            cascade=cascade,
        )

    async def preview_toggle_plugin(
        self,
        module_name: str,
        *,
        enabled: bool,
    ) -> "PluginTogglePreview":
        return await plugin_governance_service.preview_toggle_plugin(
            module_name,
            enabled=enabled,
        )

    async def uninstall_plugin(
        self,
        module_name: str,
        *,
        remove_config: bool = False,
    ) -> "PluginUninstallResult":
        return await plugin_governance_service.uninstall_plugin(
            module_name,
            remove_config=remove_config,
        )

    async def list_orphan_plugin_configs(self) -> list["OrphanPluginConfigItem"]:
        return await plugin_governance_service.list_orphan_plugin_configs()

    async def cleanup_orphan_plugin_configs(self) -> list["OrphanPluginConfigItem"]:
        return await plugin_governance_service.cleanup_orphan_plugin_configs()

    def get_adapter_config(self) -> "AdapterConfigState":
        return config_query_service.get_adapter_config()

    def update_adapter_config(self, modules: list[str]) -> "AdapterConfigState":
        return config_mutation_service.update_adapter_config(modules)

    def get_driver_config(self) -> "DriverConfigState":
        return config_query_service.get_driver_config()

    def update_driver_config(self, builtin: list[str]) -> "DriverConfigState":
        return config_mutation_service.update_driver_config(builtin)

    def get_plugin_config(self) -> "PluginConfigState":
        return config_query_service.get_plugin_config()

    def update_plugin_config(
        self,
        modules: list[str],
        dirs: list[str],
    ) -> "PluginConfigState":
        return config_mutation_service.update_plugin_config(modules, dirs)

    def get_core_view(self) -> "ConfigView":
        return config_query_service.get_core_view()

    def get_core_text(self) -> "ConfigTextView":
        return config_query_service.get_core_text()

    def update_core_view(
        self,
        values: dict[str, object | None],
        clear: list[str],
    ) -> "ConfigView":
        return config_mutation_service.update_core_view(values, clear)

    def update_core_text(self, text: str) -> "ConfigTextView":
        return config_mutation_service.update_core_text(text)

    def validate_core_text(self, text: str) -> "ConfigValidationReport":
        return config_mutation_service.validate_core_text(text)

    def get_plugin_view(self, module_name: str) -> "ConfigView":
        return config_query_service.get_plugin_view(module_name)

    def get_plugin_text(self, module_name: str) -> "ConfigTextView":
        return config_query_service.get_plugin_text(module_name)

    def update_plugin_view(
        self,
        module_name: str,
        values: dict[str, object | None],
        clear: list[str],
    ) -> "ConfigView":
        return config_mutation_service.update_plugin_view(
            module_name,
            values,
            clear,
        )

    def update_plugin_text(self, module_name: str, text: str) -> "ConfigTextView":
        return config_mutation_service.update_plugin_text(module_name, text)

    def validate_plugin_text(
        self,
        module_name: str,
        text: str,
    ) -> "ConfigValidationReport":
        return config_mutation_service.validate_plugin_text(module_name, text)


plugin_management_service = PluginManagementService()

__all__ = [
    "PluginManagementService",
    "PluginWorkspaceState",
    "plugin_management_service",
]
