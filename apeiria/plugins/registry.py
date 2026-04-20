"""Registration config views for plugins, adapters, and drivers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

import nonebot

from apeiria.config import (
    adapter_config_service,
    driver_config_service,
    plugin_config_service,
)

if TYPE_CHECKING:
    from apeiria.config.adapters import AdapterConfig
    from apeiria.config.drivers import DriverConfig
    from apeiria.config.plugins import PluginConfig


@dataclass(frozen=True)
class PluginConfigModuleStatus:
    name: str
    is_loaded: bool
    is_importable: bool


@dataclass(frozen=True)
class PluginConfigDirStatus:
    path: str
    exists: bool
    is_loaded: bool


@dataclass(frozen=True)
class AdapterConfigStatus:
    name: str
    is_loaded: bool
    is_importable: bool


@dataclass(frozen=True)
class DriverConfigStatus:
    name: str
    is_active: bool


@dataclass(frozen=True)
class PluginConfigState:
    modules: list[PluginConfigModuleStatus]
    dirs: list[PluginConfigDirStatus]


@dataclass(frozen=True)
class AdapterConfigState:
    modules: list[AdapterConfigStatus]


@dataclass(frozen=True)
class DriverConfigState:
    builtin: list[DriverConfigStatus]


class PluginRegistrationConfigService:
    """Build and persist registration state for plugins, adapters, and drivers."""

    def get_adapter_config(self) -> AdapterConfigState:
        config = adapter_config_service.read_project_adapter_config()
        return AdapterConfigState(
            modules=self._build_adapter_config_items(config["modules"]),
        )

    def update_adapter_config(self, modules: list[str]) -> AdapterConfigState:
        current = adapter_config_service.read_project_adapter_config()
        config = self._update_config_with_packages(current, modules, "modules")
        adapter_config_service.write_project_adapter_config(config)
        return AdapterConfigState(
            modules=self._build_adapter_config_items(config["modules"]),
        )

    def get_driver_config(self) -> DriverConfigState:
        config = driver_config_service.read_project_driver_config()
        return DriverConfigState(
            builtin=self._build_driver_config_items(config["builtin"]),
        )

    def update_driver_config(self, builtin: list[str]) -> DriverConfigState:
        current = driver_config_service.read_project_driver_config()
        config = self._update_config_with_packages(current, builtin, "builtin")
        driver_config_service.write_project_driver_config(config)
        return DriverConfigState(
            builtin=self._build_driver_config_items(config["builtin"]),
        )

    def get_plugin_config(self) -> PluginConfigState:
        config = plugin_config_service.read_project_plugin_config()
        return PluginConfigState(
            modules=self._build_module_config_items(config["modules"]),
            dirs=self._build_dir_config_items(config["dirs"]),
        )

    def update_plugin_config(
        self,
        modules: list[str],
        dirs: list[str],
    ) -> PluginConfigState:
        current = plugin_config_service.read_project_plugin_config()
        normalized_modules = self._normalize_entries(modules)
        normalized_dirs = self._normalize_entries(dirs)
        config: PluginConfig = {
            "modules": normalized_modules,
            "dirs": normalized_dirs,
            "packages": {
                package_name: [
                    item for item in package_modules if item in normalized_modules
                ]
                for package_name, package_modules in current["packages"].items()
            },
        }
        config["packages"] = {
            package_name: package_modules
            for package_name, package_modules in config["packages"].items()
            if package_modules
        }
        plugin_config_service.write_project_plugin_config(config)
        return PluginConfigState(
            modules=self._build_module_config_items(config["modules"]),
            dirs=self._build_dir_config_items(config["dirs"]),
        )

    def _loaded_plugin_modules(self) -> set[str]:
        return {plugin.module_name for plugin in nonebot.get_loaded_plugins()}

    def _loaded_adapter_modules(self) -> set[str]:
        return {
            self._normalize_adapter_module_name(adapter.__module__)
            for adapter in nonebot.get_adapters().values()
        }

    def _normalize_adapter_module_name(self, module_name: str) -> str:
        if module_name.endswith(".adapter"):
            return module_name[: -len(".adapter")]
        return module_name

    def _loaded_plugin_paths(self) -> list[Path]:
        result: list[Path] = []
        for plugin in nonebot.get_loaded_plugins():
            module = getattr(plugin, "module", None)
            module_file = getattr(module, "__file__", None)
            if not module_file:
                continue
            try:
                result.append(Path(module_file).resolve())
            except OSError:
                continue
        return result

    def _build_module_config_items(
        self,
        modules: list[str],
    ) -> list[PluginConfigModuleStatus]:
        loaded_modules = self._loaded_plugin_modules()
        items: list[PluginConfigModuleStatus] = []
        for module_name in modules:
            try:
                is_importable = find_spec(module_name) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                is_importable = False
            items.append(
                PluginConfigModuleStatus(
                    name=module_name,
                    is_loaded=module_name in loaded_modules,
                    is_importable=is_importable,
                )
            )
        return items

    def _build_dir_config_items(
        self,
        dirs: list[str],
    ) -> list[PluginConfigDirStatus]:
        config_root = plugin_config_service.default_config_path().parent.resolve()
        loaded_paths = self._loaded_plugin_paths()
        items: list[PluginConfigDirStatus] = []
        for raw_dir in dirs:
            directory = Path(raw_dir).expanduser()
            if not directory.is_absolute():
                directory = config_root / directory
            try:
                resolved = directory.resolve()
            except OSError:
                resolved = directory

            exists = resolved.is_dir()
            is_loaded = (
                any(
                    resolved == path.parent or resolved in path.parents
                    for path in loaded_paths
                )
                if exists
                else False
            )
            items.append(
                PluginConfigDirStatus(
                    path=raw_dir,
                    exists=exists,
                    is_loaded=is_loaded,
                )
            )
        return items

    def _build_adapter_config_items(
        self,
        modules: list[str],
    ) -> list[AdapterConfigStatus]:
        loaded_modules = self._loaded_adapter_modules()
        items: list[AdapterConfigStatus] = []
        for module_name in modules:
            try:
                is_importable = find_spec(module_name) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                is_importable = False
            items.append(
                AdapterConfigStatus(
                    name=module_name,
                    is_loaded=module_name in loaded_modules,
                    is_importable=is_importable,
                )
            )
        return items

    def _active_driver_builtin(self) -> list[str]:
        configured = getattr(nonebot.get_driver().config, "driver", None)
        if isinstance(configured, str) and configured:
            return sorted(item for item in configured.split("+") if item)
        return []

    def _build_driver_config_items(
        self,
        builtin: list[str],
    ) -> list[DriverConfigStatus]:
        active_builtin = set(self._active_driver_builtin())
        return [
            DriverConfigStatus(name=item, is_active=item in active_builtin)
            for item in builtin
        ]

    def _normalize_entries(self, values: list[str]) -> list[str]:
        return sorted({item.strip() for item in values if item.strip()})

    @overload
    def _update_config_with_packages(
        self,
        current: AdapterConfig,
        entries: list[str],
        key: Literal["modules"],
    ) -> AdapterConfig: ...

    @overload
    def _update_config_with_packages(
        self,
        current: DriverConfig,
        entries: list[str],
        key: Literal["builtin"],
    ) -> DriverConfig: ...

    def _update_config_with_packages(
        self,
        current: AdapterConfig | DriverConfig,
        entries: list[str],
        key: Literal["modules", "builtin"],
    ) -> AdapterConfig | DriverConfig:
        normalized = self._normalize_entries(entries)
        packages = {
            package_name: [item for item in items if item in normalized]
            for package_name, items in current["packages"].items()
        }
        packages = {
            package_name: items for package_name, items in packages.items() if items
        }
        if key == "modules":
            return {
                "modules": normalized,
                "packages": packages,
            }
        return {
            "builtin": normalized,
            "packages": packages,
        }


plugin_registration_config_service = PluginRegistrationConfigService()

__all__ = [
    "AdapterConfigState",
    "AdapterConfigStatus",
    "DriverConfigState",
    "DriverConfigStatus",
    "PluginConfigDirStatus",
    "PluginConfigModuleStatus",
    "PluginConfigState",
    "PluginRegistrationConfigService",
    "plugin_registration_config_service",
]
