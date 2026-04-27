"""Runtime state discovery for governance-facing plugin catalog views."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import packages_distributions
from typing import TYPE_CHECKING

import nonebot

from apeiria._framework_loader import iter_builtin_plugin_modules
from apeiria.config.plugins import plugin_config_service
from apeiria.plugins.metadata.module_cache import is_module_importable
from apeiria.plugins.state import get_disabled_plugin_modules
from apeiria.utils.plugin_introspection import (
    get_module_required_plugins,
    get_pending_uninstall_plugin_modules,
    get_plugin_name,
    get_plugin_required_plugins,
    get_plugin_source,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from nonebot.plugin import Plugin

    from apeiria.plugins.repository import PluginStateRow


@dataclass(frozen=True)
class PluginListContext:
    enabled_map: dict[str, bool]
    info_map: "Mapping[str, PluginStateRow]"
    package_bindings: dict[str, list[str]]
    pending_uninstall_modules: set[str]
    top_level_packages: "Mapping[str, list[str]]"


@dataclass(frozen=True)
class PluginItemFacts:
    is_explicit: bool
    is_dependency: bool
    required_plugins: list[str]
    dependent_plugins: list[str]


@dataclass(frozen=True)
class PluginCatalogState:
    context: PluginListContext
    loaded_plugins: dict[str, "Plugin"]
    explicit_modules: set[str]
    disabled_modules: set[str]
    required_by_module: dict[str, list[str]]
    display_name_by_module: dict[str, str]
    dependency_modules: set[str]
    candidate_modules: set[str]


class PluginCatalogStateBuilder:
    """Build runtime state needed to render the plugin catalog."""

    async def build_catalog_state(self) -> PluginCatalogState:
        from apeiria.plugins.repository import plugin_catalog_repository

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

        pending_uninstall_modules = self.expand_pending_uninstall_modules(
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
        return PluginCatalogState(
            context=PluginListContext(
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

    def build_dependent_name_map(
        self,
        catalog: PluginCatalogState,
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

    def build_plugin_facts(
        self,
        module_name: str,
        *,
        catalog: PluginCatalogState,
        dependent_plugins: list[str],
    ) -> PluginItemFacts:
        return PluginItemFacts(
            is_explicit=module_name in catalog.explicit_modules,
            is_dependency=module_name in catalog.dependency_modules,
            required_plugins=catalog.required_by_module.get(module_name, []),
            dependent_plugins=dependent_plugins,
        )

    def expand_pending_uninstall_modules(
        self,
        *,
        loaded_plugins: dict[str, "Plugin"],
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


plugin_catalog_state_builder = PluginCatalogStateBuilder()
