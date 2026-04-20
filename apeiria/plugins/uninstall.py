"""Plugin uninstall operations."""

from __future__ import annotations

from importlib.metadata import distributions, packages_distributions
from pathlib import Path
from typing import TYPE_CHECKING

import nonebot

from apeiria.config.plugins import plugin_config_service
from apeiria.config.project import project_config_service
from apeiria.environment.extension_project import (
    declared_plugin_requirements,
    enqueue_plugin_module_uninstall,
    enqueue_plugin_requirement_removal,
    resolve_declared_plugin_requirement,
)
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.plugins.models import PluginUninstallResult
from apeiria.plugins.package_ids import normalize_package_id
from apeiria.plugins.settings_support import get_plugin_declared_configs
from apeiria.utils.plugin_introspection import (
    find_loaded_plugin,
    get_pending_uninstall_plugin_modules,
    get_plugin_required_plugins,
    get_plugin_source,
    invalidate_plugin_management_caches,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from nonebot.plugin import Plugin


class PluginUninstallService:
    """Own plugin uninstall planning and mutation."""

    async def uninstall_plugin(
        self,
        module_name: str,
        *,
        remove_config: bool = False,
        get_uninstall_block_reason: Callable[[str], str | None],
        expand_pending_uninstall_modules: Callable[..., set[str]],
    ) -> PluginUninstallResult:
        plugin = find_loaded_plugin(module_name)
        if plugin is None:
            raise ResourceNotFoundError(module_name)

        reason = get_uninstall_block_reason(module_name)
        if reason:
            raise ProtectedPluginError(reason)
        if not self._is_plugin_uninstallable(plugin):
            msg = "only custom or external plugins can be uninstalled"
            raise ValueError(msg)

        current_config = plugin_config_service.read_project_plugin_config()
        loaded_plugins = {
            loaded.module_name: loaded for loaded in nonebot.get_loaded_plugins()
        }
        required_by_module = {
            loaded.module_name: get_plugin_required_plugins(loaded)
            for loaded in loaded_plugins.values()
        }
        explicit_modules = set(current_config["modules"])
        pending_modules = expand_pending_uninstall_modules(
            loaded_plugins=loaded_plugins,
            explicit_modules=explicit_modules,
            seed_modules=get_pending_uninstall_plugin_modules() | {module_name},
            required_by_module=required_by_module,
        )
        package_name = self._resolve_installed_package(module_name, plugin)
        removal_requirement = self._resolve_removal_requirement(
            module_name,
            package_name,
            current_config["packages"],
        )
        for pending_module in sorted(pending_modules):
            plugin_config_service.remove_project_plugin_module(pending_module)
            enqueue_plugin_module_uninstall(pending_module)
        if remove_config:
            for pending_module in sorted(pending_modules):
                if pending_module != module_name:
                    continue
                section = get_plugin_declared_configs(pending_module).section
                project_config_service.remove_project_plugin_section(section)
        if removal_requirement:
            enqueue_plugin_requirement_removal(removal_requirement)
        invalidate_plugin_management_caches()
        return PluginUninstallResult(
            requirement=removal_requirement or "",
            module_names=sorted(pending_modules),
        )

    def _resolve_installed_package(
        self,
        module_name: str,
        plugin: object | None = None,
    ) -> str | None:
        packages = plugin_config_service.read_project_plugin_config()["packages"]
        listed = self._resolve_listed_installed_package(
            module_name,
            packages,
            packages_distributions(),
        )
        if listed:
            return listed
        return self._infer_installed_package_from_module_file(plugin)

    def _resolve_listed_installed_package(
        self,
        module_name: str,
        package_bindings: dict[str, list[str]],
        top_level_packages: object,
    ) -> str | None:
        if not isinstance(top_level_packages, dict):
            return None
        for package_name, module_names in package_bindings.items():
            if module_name in module_names:
                return package_name
        top_level = module_name.split(".", 1)[0]
        inferred = top_level_packages.get(top_level, [])
        return inferred[0] if inferred else None

    def _infer_installed_package_from_module_file(
        self,
        plugin: object | None = None,
    ) -> str | None:
        module = getattr(plugin, "module", None)
        module_file = getattr(module, "__file__", None)
        if not isinstance(module_file, str) or not module_file:
            return None

        try:
            module_path = Path(module_file).resolve()
        except OSError:
            return None

        for dist in distributions():
            dist_name = str(dist.metadata["Name"] or dist.name).strip()
            if not dist_name:
                continue
            for file in dist.files or ():
                try:
                    candidate = Path(str(dist.locate_file(file))).resolve()
                except OSError:
                    continue
                if candidate == module_path:
                    return dist_name
        return None

    def _resolve_removal_requirement(
        self,
        module_name: str,
        package_name: str | None,
        package_bindings: dict[str, list[str]],
    ) -> str | None:
        if not package_name:
            return None

        declared = resolve_declared_plugin_requirement(package_name).strip()
        if not declared:
            return None

        normalized_declared = normalize_package_id(declared)
        if normalized_declared not in declared_plugin_requirements():
            return None

        bound_modules = package_bindings.get(package_name, [])
        if not bound_modules:
            return declared
        if len(bound_modules) == 1 and module_name in bound_modules:
            return declared
        return None

    def _is_plugin_uninstallable(self, plugin: "Plugin") -> bool:
        return get_plugin_source(plugin) in {"custom", "external"}


plugin_uninstall_service = PluginUninstallService()
