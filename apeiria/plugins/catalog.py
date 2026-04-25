"""Plugin domain services."""

from __future__ import annotations

from dataclasses import dataclass, replace
from importlib.metadata import packages_distributions
from typing import TYPE_CHECKING

import nonebot

from apeiria._framework_loader import iter_builtin_plugin_modules
from apeiria.config.plugins import plugin_config_service
from apeiria.exceptions import ResourceNotFoundError
from apeiria.i18n import t
from apeiria.plugins.metadata.api import (
    PluginExtraData,
    normalize_plugin_type_value,
)
from apeiria.plugins.metadata.builders import (
    handler_descriptor_builder,
    plugin_descriptor_builder,
)
from apeiria.plugins.metadata.module_cache import is_module_importable
from apeiria.plugins.models import (
    PluginCatalogEntry,
    PluginDescriptor,
    PluginGovernanceState,
    PluginPackageBinding,
    PluginRuntimeState,
    PluginUninstallResult,
)
from apeiria.plugins.policy import plugin_policy_service
from apeiria.plugins.protection import is_framework_dependency_plugin_module
from apeiria.plugins.readme import PluginReadme, plugin_readme_service
from apeiria.plugins.repository import plugin_catalog_repository
from apeiria.plugins.settings_cleanup import (
    OrphanPluginConfigItem,
    plugin_config_cleanup_service,
)
from apeiria.plugins.state import get_disabled_plugin_modules
from apeiria.plugins.toggle import (
    PluginTogglePreview,
    PluginToggleResult,
    plugin_toggle_service,
)
from apeiria.plugins.uninstall import plugin_uninstall_service
from apeiria.utils.plugin_introspection import (
    find_loaded_plugin,
    get_module_required_plugins,
    get_pending_uninstall_plugin_modules,
    get_plugin_name,
    get_plugin_required_plugins,
    get_plugin_source,
    get_plugin_source_by_module_name,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from nonebot.plugin import Plugin

    from apeiria.plugins.repository import PluginStateRow


@dataclass(frozen=True)
class _PluginListContext:
    enabled_map: dict[str, bool]
    info_map: "Mapping[str, PluginStateRow]"
    package_bindings: dict[str, list[str]]
    pending_uninstall_modules: set[str]
    top_level_packages: "Mapping[str, list[str]]"


@dataclass(frozen=True)
class _PluginItemFacts:
    is_explicit: bool
    is_dependency: bool
    required_plugins: list[str]
    dependent_plugins: list[str]


@dataclass(frozen=True)
class _PluginCatalogState:
    context: _PluginListContext
    loaded_plugins: dict[str, Plugin]
    explicit_modules: set[str]
    disabled_modules: set[str]
    required_by_module: dict[str, list[str]]
    display_name_by_module: dict[str, str]
    dependency_modules: set[str]
    candidate_modules: set[str]


class PluginGovernanceService:
    """List and mutate governance-facing plugin state."""

    async def list_plugins(self) -> list[PluginCatalogEntry]:
        policy_map = await plugin_catalog_repository.get_plugin_policy_map()
        catalog = await self._build_catalog_state()
        dependent_name_map = self._build_dependent_name_map(catalog)

        items: list[PluginCatalogEntry] = []
        for module_name in sorted(catalog.candidate_modules):
            facts = self._build_plugin_facts(
                module_name,
                catalog=catalog,
                dependent_plugins=sorted(dependent_name_map.get(module_name, set())),
            )
            plugin = catalog.loaded_plugins.get(module_name)
            access_mode = (
                policy_map[module_name].access_mode
                if module_name in policy_map
                else "default_allow"
            )

            if plugin is not None:
                plugin_item = self._build_loaded_plugin_entry(
                    plugin=plugin,
                    context=catalog.context,
                    facts=facts,
                    access_mode=access_mode,
                )
                if plugin_item is not None:
                    items.append(plugin_item)
                continue

            plugin_item = self._build_unloaded_plugin_entry(
                module_name=module_name,
                context=catalog.context,
                facts=facts,
                access_mode=access_mode,
            )
            if plugin_item is not None:
                items.append(plugin_item)
        return self._collapse_child_plugins(items)

    async def get_plugin(self, module_name: str) -> PluginCatalogEntry | None:
        catalog = await self._build_catalog_state()
        if module_name not in catalog.candidate_modules:
            return None

        facts = self._build_plugin_facts(
            module_name,
            catalog=catalog,
            dependent_plugins=sorted(
                self._build_dependent_name_map(catalog).get(module_name, set())
            ),
        )
        policy = await plugin_catalog_repository.get_plugin_policy(module_name)
        access_mode = policy.access_mode if policy else "default_allow"

        plugin = catalog.loaded_plugins.get(module_name)
        if plugin is not None:
            return self._build_loaded_plugin_entry(
                plugin=plugin,
                context=catalog.context,
                facts=facts,
                access_mode=access_mode,
            )
        return self._build_unloaded_plugin_entry(
            module_name=module_name,
            context=catalog.context,
            facts=facts,
            access_mode=access_mode,
        )

    async def get_plugin_readme(self, module_name: str) -> PluginReadme:
        item = await self.get_plugin(module_name)
        if item is None:
            raise ResourceNotFoundError(module_name)
        return plugin_readme_service.get_plugin_readme(module_name)

    async def get_plugin_readme_asset_path(
        self,
        module_name: str,
        relative_path: str,
    ) -> Path:
        item = await self.get_plugin(module_name)
        if item is None:
            raise ResourceNotFoundError(module_name)
        return plugin_readme_service.get_plugin_readme_asset_path(
            module_name,
            relative_path,
        )

    async def set_plugin_enabled(self, module_name: str, *, enabled: bool) -> bool:
        result = await self.apply_plugin_toggle(
            module_name,
            enabled=enabled,
            cascade=False,
        )
        return bool(result.affected_modules)

    async def apply_plugin_toggle(
        self,
        module_name: str,
        *,
        enabled: bool,
        cascade: bool = False,
    ) -> PluginToggleResult:
        return await plugin_toggle_service.apply_plugin_toggle(
            module_name,
            enabled=enabled,
            cascade=cascade,
            list_plugins=self.list_plugins,
            set_plugin_enabled_record=self._set_plugin_enabled_record,
        )

    async def preview_toggle_plugin(
        self,
        module_name: str,
        *,
        enabled: bool,
    ) -> PluginTogglePreview:
        return await plugin_toggle_service.preview_toggle_plugin(
            module_name,
            enabled=enabled,
            list_plugins=self.list_plugins,
        )

    async def _resolve_protection_reason(self, module_name: str) -> str | None:
        items = await self.list_plugins()
        item = next(
            (entry for entry in items if entry.descriptor.module_name == module_name),
            None,
        )
        if item is not None:
            return item.governance_state.protected_reason
        reasons = self._collect_core_block_reasons(module_name)
        return "；".join(reasons) if reasons else None

    async def _set_plugin_enabled_record(
        self,
        module_name: str,
        *,
        enabled: bool,
    ) -> bool:
        plugin = find_loaded_plugin(module_name)
        try:
            changed = await plugin_catalog_repository.set_plugin_enabled(
                module_name,
                enabled=enabled,
            )
        except ResourceNotFoundError:
            if plugin is not None:
                await plugin_catalog_repository.ensure_plugin_record(plugin)
            elif is_module_importable(module_name):
                await plugin_catalog_repository.ensure_plugin_record_by_module_name(
                    module_name
                )
            else:
                raise ResourceNotFoundError(module_name) from None
            changed = await plugin_catalog_repository.set_plugin_enabled(
                module_name,
                enabled=enabled,
            )

        return changed

    async def uninstall_plugin(
        self,
        module_name: str,
        *,
        remove_config: bool = False,
    ) -> PluginUninstallResult:
        return await plugin_uninstall_service.uninstall_plugin(
            module_name,
            remove_config=remove_config,
            get_uninstall_block_reason=self._get_uninstall_block_reason,
            expand_pending_uninstall_modules=self._expand_pending_uninstall_modules,
        )

    async def list_orphan_plugin_configs(self) -> list[OrphanPluginConfigItem]:
        return await plugin_config_cleanup_service.list_orphan_plugin_configs()

    async def cleanup_orphan_plugin_configs(self) -> list[OrphanPluginConfigItem]:
        return await plugin_config_cleanup_service.cleanup_orphan_plugin_configs()

    async def _build_catalog_state(self) -> _PluginCatalogState:
        enabled_map = await plugin_catalog_repository.get_enabled_map()
        info_map = await plugin_catalog_repository.get_plugin_info_map()
        project_plugin_config = plugin_config_service.read_project_plugin_config()
        explicit_modules = set(project_plugin_config["modules"])
        builtin_modules = set(iter_builtin_plugin_modules())
        loaded_plugins = {
            plugin.module_name: plugin for plugin in nonebot.get_loaded_plugins()
        }
        required_by_module: dict[str, list[str]] = {}
        display_name_by_module: dict[str, str] = {}

        for loaded_module_name, plugin in loaded_plugins.items():
            required_by_module[loaded_module_name] = get_plugin_required_plugins(plugin)
            display_name_by_module[loaded_module_name] = get_plugin_name(plugin)

        pending_uninstall_modules = self._expand_pending_uninstall_modules(
            loaded_plugins=loaded_plugins,
            explicit_modules=explicit_modules,
            seed_modules=get_pending_uninstall_plugin_modules(),
            required_by_module=required_by_module,
        )
        loaded_modules = set(loaded_plugins)
        unloaded_declared_modules = (
            explicit_modules | builtin_modules
        ) - loaded_modules
        for unloaded_module_name in sorted(unloaded_declared_modules):
            required_by_module[unloaded_module_name] = get_module_required_plugins(
                unloaded_module_name
            )
            display_name_by_module.setdefault(
                unloaded_module_name,
                unloaded_module_name,
            )

        dependency_modules = {
            dependency
            for dependencies in required_by_module.values()
            for dependency in dependencies
        }
        visible_dependency_modules = {
            dependency
            for dependency in dependency_modules
            if is_module_importable(dependency)
        }
        return _PluginCatalogState(
            context=_PluginListContext(
                enabled_map=enabled_map,
                info_map=info_map,
                package_bindings=project_plugin_config["packages"],
                pending_uninstall_modules=pending_uninstall_modules,
                top_level_packages=packages_distributions(),
            ),
            loaded_plugins=loaded_plugins,
            explicit_modules=explicit_modules,
            disabled_modules=await get_disabled_plugin_modules(),
            required_by_module=required_by_module,
            display_name_by_module=display_name_by_module,
            dependency_modules=dependency_modules,
            candidate_modules=(
                loaded_modules
                | explicit_modules
                | builtin_modules
                | visible_dependency_modules
            ),
        )

    def _build_dependent_name_map(
        self,
        catalog: _PluginCatalogState,
    ) -> dict[str, set[str]]:
        dependent_name_map: dict[str, set[str]] = {
            module_name: set() for module_name in catalog.candidate_modules
        }
        for owner_module, dependencies in catalog.required_by_module.items():
            if owner_module in catalog.context.pending_uninstall_modules:
                continue
            if owner_module in catalog.disabled_modules:
                continue
            owner_name = catalog.display_name_by_module.get(owner_module, owner_module)
            for dependency in dependencies:
                dependent_name_map.setdefault(dependency, set()).add(owner_name)
        return dependent_name_map

    def _build_plugin_facts(
        self,
        module_name: str,
        *,
        catalog: _PluginCatalogState,
        dependent_plugins: list[str],
    ) -> _PluginItemFacts:
        return _PluginItemFacts(
            is_explicit=module_name in catalog.explicit_modules,
            is_dependency=module_name in catalog.dependency_modules,
            required_plugins=catalog.required_by_module.get(module_name, []),
            dependent_plugins=dependent_plugins,
        )

    def _resolve_listed_installed_package(
        self,
        module_name: str,
        package_bindings: dict[str, list[str]],
        top_level_packages: "Mapping[str, list[str]]",
    ) -> str | None:
        for package_name, module_names in package_bindings.items():
            if module_name in module_names:
                return package_name
        top_level = module_name.split(".", 1)[0]
        inferred = top_level_packages.get(top_level, [])
        return inferred[0] if inferred else None

    def _build_loaded_plugin_entry(
        self,
        *,
        plugin: Plugin,
        context: _PluginListContext,
        facts: _PluginItemFacts,
        access_mode: str,
    ) -> PluginCatalogEntry | None:
        descriptor = plugin_descriptor_builder.build(plugin)
        if descriptor.is_ui_hidden:
            return None
        extra = (
            PluginExtraData.from_extra(plugin.metadata.extra)
            if plugin.metadata and plugin.metadata.extra
            else None
        )
        installed_package = self._resolve_listed_installed_package(
            plugin.module_name,
            context.package_bindings,
            context.top_level_packages,
        )
        protected_reason = self._compose_protection_reason(
            plugin.module_name,
            facts.dependent_plugins,
        )
        can_enable_disable = (
            plugin.module_name not in context.pending_uninstall_modules
            and not is_framework_dependency_plugin_module(plugin.module_name)
        )
        uninstall_block_reason = self._get_uninstall_block_reason(plugin.module_name)
        can_uninstall = (
            facts.is_explicit
            and can_enable_disable
            and descriptor.source in {"custom", "external"}
            and uninstall_block_reason is None
        )
        return PluginCatalogEntry(
            descriptor=descriptor,
            runtime_state=PluginRuntimeState(
                is_loaded=True,
                is_pending_uninstall=(
                    plugin.module_name in context.pending_uninstall_modules
                ),
            ),
            governance_state=PluginGovernanceState(
                kind=plugin_policy_service.get_kind(plugin.module_name),
                access_mode=access_mode,
                is_global_enabled=context.enabled_map.get(plugin.module_name, True),
                is_protected=protected_reason is not None,
                protected_reason=protected_reason,
                is_explicit=facts.is_explicit,
                is_dependency=facts.is_dependency,
                can_edit_config=True,
                can_view_readme=plugin_readme_service.resolve_plugin_readme_path(
                    plugin.module_name,
                    plugin=plugin,
                )
                is not None,
                can_enable_disable=can_enable_disable,
                can_uninstall=can_uninstall,
                required_plugins=facts.required_plugins,
                dependent_plugins=facts.dependent_plugins,
            ),
            handler_descriptors=handler_descriptor_builder.build_for_plugin(plugin),
            package_binding=PluginPackageBinding(
                installed_package=installed_package,
                installed_module_names=sorted(
                    context.package_bindings.get(installed_package, [])
                )
                if installed_package in context.package_bindings
                else [plugin.module_name]
                if installed_package
                else [],
            ),
            ui_order=extra.ui.order if extra is not None else 99,
        )

    def _build_unloaded_plugin_entry(
        self,
        *,
        module_name: str,
        context: _PluginListContext,
        facts: _PluginItemFacts,
        access_mode: str,
    ) -> PluginCatalogEntry | None:
        persisted = context.info_map.get(module_name)
        if persisted is not None and bool(getattr(persisted, "is_ui_hidden", False)):
            return None
        installed_package = self._resolve_listed_installed_package(
            module_name,
            context.package_bindings,
            context.top_level_packages,
        )
        protected_reason = self._compose_protection_reason(
            module_name,
            facts.dependent_plugins,
        )
        is_importable = is_module_importable(module_name)
        can_enable_disable = (
            is_importable
            and module_name not in context.pending_uninstall_modules
            and protected_reason is None
        )
        return PluginCatalogEntry(
            descriptor=PluginDescriptor(
                module_name=module_name,
                name=persisted.name if persisted and persisted.name else module_name,
                description=persisted.description if persisted else None,
                homepage=None,
                source=get_plugin_source_by_module_name(module_name),
                plugin_type=(
                    normalize_plugin_type_value(persisted.plugin_type)
                    if persisted
                    else "normal"
                ),
                admin_level=persisted.admin_level if persisted else 0,
                author=persisted.author if persisted else None,
                version=persisted.version if persisted else None,
                is_ui_hidden=bool(getattr(persisted, "is_ui_hidden", False)),
            ),
            runtime_state=PluginRuntimeState(
                is_loaded=False,
                is_pending_uninstall=(module_name in context.pending_uninstall_modules),
            ),
            governance_state=PluginGovernanceState(
                kind=plugin_policy_service.get_kind(module_name),
                access_mode=access_mode,
                is_global_enabled=context.enabled_map.get(
                    module_name,
                    facts.is_explicit,
                ),
                is_protected=protected_reason is not None,
                protected_reason=protected_reason,
                is_explicit=facts.is_explicit,
                is_dependency=facts.is_dependency,
                can_edit_config=is_importable or facts.is_explicit,
                can_view_readme=plugin_readme_service.resolve_plugin_readme_path(
                    module_name
                )
                is not None,
                can_enable_disable=can_enable_disable,
                can_uninstall=False,
                required_plugins=facts.required_plugins,
                dependent_plugins=facts.dependent_plugins,
            ),
            package_binding=PluginPackageBinding(
                installed_package=installed_package,
                installed_module_names=sorted(
                    context.package_bindings.get(installed_package, [])
                )
                if installed_package in context.package_bindings
                else [module_name]
                if installed_package
                else [],
            ),
            ui_order=99,
        )

    def _compose_protection_reason(
        self,
        module_name: str,
        dependent_plugins: list[str],
    ) -> str | None:
        reasons = self._collect_core_block_reasons(module_name)
        if dependent_plugins:
            reasons.append(
                t(
                    "common.required_by_plugins",
                    plugins=", ".join(dependent_plugins),
                )
            )
        return "；".join(reasons) if reasons else None

    def _get_uninstall_block_reason(self, module_name: str) -> str | None:
        reasons = self._collect_core_block_reasons(module_name)
        return "；".join(reasons) if reasons else None

    def _collect_core_block_reasons(self, module_name: str) -> list[str]:
        reasons: list[str] = []
        if is_framework_dependency_plugin_module(module_name):
            reasons.append(t("common.framework_required"))
        if module_name == "apeiria.builtin_plugins.web_ui":
            reasons.append(t("common.control_panel_required"))
        return reasons

    def _expand_pending_uninstall_modules(
        self,
        *,
        loaded_plugins: dict[str, Plugin],
        explicit_modules: set[str],
        seed_modules: set[str],
        required_by_module: dict[str, list[str]],
    ) -> set[str]:
        pending = set(seed_modules) & set(loaded_plugins)
        if not pending:
            return pending

        while True:
            changed = False
            for module_name, plugin in loaded_plugins.items():
                if module_name in pending:
                    continue
                if module_name in explicit_modules:
                    continue
                plugin_source = get_plugin_source(plugin)
                if plugin_source not in {"custom", "external"}:
                    continue

                owners = {
                    owner_module
                    for owner_module, dependencies in required_by_module.items()
                    if module_name in dependencies
                }
                if owners and owners <= pending:
                    pending.add(module_name)
                    changed = True
            if not changed:
                return pending

    def _collapse_child_plugins(
        self,
        items: list[PluginCatalogEntry],
    ) -> list[PluginCatalogEntry]:
        item_map = {item.descriptor.module_name: item for item in items}
        child_map: dict[str, list[str]] = {}
        hidden_children: set[str] = set()

        for item in items:
            parent_module = self._resolve_parent_plugin_module(item, item_map)
            if parent_module is None:
                continue
            child_map.setdefault(parent_module, []).append(item.descriptor.module_name)
            hidden_children.add(item.descriptor.module_name)

        collapsed: list[PluginCatalogEntry] = []
        for item in items:
            if item.descriptor.module_name in hidden_children:
                continue
            child_plugins = sorted(
                child_map.get(item.descriptor.module_name, []),
            )
            next_item = item
            if child_plugins:
                next_item = replace(item, child_plugin_modules=child_plugins)
            collapsed.append(next_item)
        collapsed.sort(
            key=lambda entry: (
                entry.ui_order,
                entry.descriptor.name.lower()
                if entry.descriptor.name
                else entry.descriptor.module_name.lower(),
            ),
        )
        return collapsed

    def _resolve_parent_plugin_module(
        self,
        item: PluginCatalogEntry,
        item_map: dict[str, PluginCatalogEntry],
    ) -> str | None:
        if not item.runtime_state.is_loaded or item.governance_state.is_explicit:
            return None

        parent_module = item.descriptor.module_name.rpartition(".")[0]
        while parent_module:
            parent_item = item_map.get(parent_module)
            if parent_item is not None and parent_item.runtime_state.is_loaded:
                return parent_module
            parent_module = parent_module.rpartition(".")[0]
        return None


plugin_governance_service = PluginGovernanceService()
