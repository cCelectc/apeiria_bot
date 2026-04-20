from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, cast

import nonebot

from apeiria.config.package_config import (
    add_unique_sorted_item,
    bind_package_item,
    get_package_bound_items,
    normalize_package_item_map,
    normalize_string_list,
    remove_item_from_config_packages,
    unbind_package_item,
)
from apeiria.plugins.state import (
    get_disabled_plugin_modules_sync,
)
from apeiria.utils.files import atomic_write_text, load_toml_dict

if TYPE_CHECKING:
    from collections.abc import Sequence


class PluginConfig(TypedDict):
    modules: list[str]
    dirs: list[str]
    packages: dict[str, list[str]]


logger = logging.getLogger("apeiria.config.plugins")


class PluginConfigService:
    """Manage project plugin module, dir, and package bindings."""

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def default_config_path(self) -> Path:
        return self._project_root() / "apeiria.plugins.toml"

    def read_project_plugin_config(
        self,
        config_path: Path | None = None,
    ) -> PluginConfig:
        target = config_path or self.default_config_path()
        return self._normalize_config(self._load_config(target))

    def write_project_plugin_config(
        self,
        config: PluginConfig,
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        atomic_write_text(target, self._dump_config(config))
        return target

    def ensure_project_plugin_config(self, config_path: Path | None = None) -> Path:
        target = config_path or self.default_config_path()
        if not target.exists():
            self.write_project_plugin_config(
                {"modules": [], "dirs": [], "packages": {}},
                target,
            )
        return target

    def add_project_plugin_module(
        self,
        module_name: str,
        config_path: Path | None = None,
    ) -> PluginConfig:
        config = self.read_project_plugin_config(config_path)
        if add_unique_sorted_item(config["modules"], module_name):
            self.write_project_plugin_config(config, config_path)
        return config

    def remove_project_plugin_module(
        self,
        module_name: str,
        config_path: Path | None = None,
    ) -> PluginConfig:
        config = self.read_project_plugin_config(config_path)
        remove_item_from_config_packages(
            cast("dict[str, Any]", config),
            items_key="modules",
            item=module_name,
        )
        self.write_project_plugin_config(config, config_path)
        return config

    def add_project_plugin_dir(
        self,
        directory: str,
        config_path: Path | None = None,
    ) -> PluginConfig:
        config = self.read_project_plugin_config(config_path)
        if add_unique_sorted_item(config["dirs"], directory):
            self.write_project_plugin_config(config, config_path)
        return config

    def remove_project_plugin_dir(
        self,
        directory: str,
        config_path: Path | None = None,
    ) -> PluginConfig:
        config = self.read_project_plugin_config(config_path)
        config["dirs"] = [item for item in config["dirs"] if item != directory]
        self.write_project_plugin_config(config, config_path)
        return config

    def load_project_plugins(self, config_path: Path | None = None) -> None:
        """Load configured plugins while skipping ones already loaded by NoneBot."""
        target = config_path or self.default_config_path()
        config = self.read_project_plugin_config(target)
        modules = config["modules"]
        directories = self._resolve_dirs(target, config["dirs"])

        loaded_modules = {
            plugin.module_name
            for plugin in nonebot.get_loaded_plugins()
            if getattr(plugin, "module_name", None)
        }
        modules = [module for module in modules if module not in loaded_modules]
        disabled_modules = get_disabled_plugin_modules_sync(modules)
        modules = [module for module in modules if module not in disabled_modules]

        existing_dirs: list[str] = []
        for directory in directories:
            if not directory.is_dir():
                logger.warning(
                    "Skip loading plugin dir %s: directory not found",
                    directory,
                )
                continue
            existing_dirs.append(str(directory))

        nonebot.load_all_plugins(modules, existing_dirs)

    def bind_project_plugin_package(
        self,
        package_name: str,
        module_name: str,
        config_path: Path | None = None,
    ) -> PluginConfig:
        """Bind an installed package to the module it contributed to project config."""
        config = self.add_project_plugin_module(module_name, config_path)
        bind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            item=module_name,
        )
        self.write_project_plugin_config(config, config_path)
        return config

    def get_project_plugin_package_modules(
        self,
        package_name: str,
        config_path: Path | None = None,
    ) -> list[str]:
        config = self.read_project_plugin_config(config_path)
        return get_package_bound_items(
            cast("dict[str, Any]", config),
            package_name=package_name,
        )

    def unbind_project_plugin_package(
        self,
        package_name: str,
        module_name: str | None = None,
        config_path: Path | None = None,
    ) -> PluginConfig:
        config = self.read_project_plugin_config(config_path)
        changed = unbind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            items_key="modules",
            item=module_name,
        )
        if not changed:
            return config
        self.write_project_plugin_config(config, config_path)
        return config

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        return load_toml_dict(
            config_path,
            logger=logger,
            missing_dependency_message=(
                "Skip loading apeiria.plugins.toml: tomllib/tomli is unavailable"
            ),
        )

    def _normalize_config(self, data: dict[str, Any]) -> PluginConfig:
        plugin_config = data.get("plugins")
        if not isinstance(plugin_config, dict):
            return {"modules": [], "dirs": [], "packages": {}}
        package_config = data.get("plugin_packages")
        return {
            "modules": normalize_string_list(
                plugin_config.get("modules"),
                ignore_literal_null=True,
            ),
            "dirs": normalize_string_list(
                plugin_config.get("dirs"),
                ignore_literal_null=True,
            ),
            "packages": normalize_package_item_map(package_config),
        }

    def _dump_config(self, config: PluginConfig) -> str:
        def _dump_list(values: Sequence[str]) -> str:
            return ", ".join(f'"{value}"' for value in values)

        lines = [
            "[plugins]",
            f"modules = [{_dump_list(config['modules'])}]",
            f"dirs = [{_dump_list(config['dirs'])}]",
            "",
        ]
        if config["packages"]:
            lines.append("[plugin_packages]")
            lines.extend(
                f'"{package_name}" = [{_dump_list(config["packages"][package_name])}]'
                for package_name in sorted(config["packages"])
            )
            lines.append("")
        return "\n".join(lines)

    def _resolve_dirs(
        self,
        config_path: Path,
        directories: Sequence[str],
    ) -> list[Path]:
        base_dir = config_path.parent
        resolved_dirs: list[Path] = []
        for raw_dir in directories:
            path = Path(raw_dir).expanduser()
            if not path.is_absolute():
                path = base_dir / path
            resolved_dirs.append(path.resolve())
        return resolved_dirs


plugin_config_service = PluginConfigService()
