from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, TypedDict, cast

from nonebot.log import logger

from apeiria.config.package_config import (
    bind_package_item,
    get_package_bound_items,
    normalize_package_item_map,
    normalize_string_list,
    remove_item_from_config_packages,
    unbind_package_item,
)
from apeiria.utils.files import atomic_write_text, load_toml_dict
from apeiria.utils.project_context import current_project_root

if TYPE_CHECKING:
    from pathlib import Path


class DriverConfig(TypedDict):
    builtin: list[str]
    packages: dict[str, list[str]]


class DriverConfigService:
    """Manage project driver config and package bindings."""

    def _project_root(self) -> Path:
        return current_project_root()

    def default_config_path(self) -> Path:
        return self._project_root() / "apeiria.drivers.toml"

    def read_project_driver_config(
        self,
        config_path: Path | None = None,
    ) -> DriverConfig:
        target = config_path or self.default_config_path()
        return self._normalize_config(self._load_config(target))

    def write_project_driver_config(
        self,
        config: DriverConfig,
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        atomic_write_text(target, self._dump_config(config))
        return target

    def ensure_project_driver_config(self, config_path: Path | None = None) -> Path:
        target = config_path or self.default_config_path()
        if not target.exists():
            self.write_project_driver_config({"builtin": [], "packages": {}}, target)
        return target

    def add_project_driver_builtin(
        self,
        builtin_name: str,
        config_path: Path | None = None,
    ) -> DriverConfig:
        config = self.read_project_driver_config(config_path)
        if builtin_name not in config["builtin"]:
            config["builtin"] = self._merge_driver_builtin(
                config["builtin"],
                builtin_name,
            )
            self.write_project_driver_config(config, config_path)
        return config

    def remove_project_driver_builtin(
        self,
        builtin_name: str,
        config_path: Path | None = None,
    ) -> DriverConfig:
        config = self.read_project_driver_config(config_path)
        remove_item_from_config_packages(
            cast("dict[str, Any]", config),
            items_key="builtin",
            item=builtin_name,
        )
        self.write_project_driver_config(config, config_path)
        return config

    def get_project_driver_kwargs(
        self,
        config_path: Path | None = None,
    ) -> dict[str, str]:
        """Return the effective driver kwargs passed into `nonebot.init()`."""
        config = self.read_project_driver_config(config_path)
        builtin = self.effective_driver_builtin(config["builtin"])
        if not builtin:
            return {}
        return {"driver": "+".join(builtin)}

    def bind_project_driver_package(
        self,
        package_name: str,
        builtin_name: str,
        config_path: Path | None = None,
    ) -> DriverConfig:
        config = self.add_project_driver_builtin(builtin_name, config_path)
        bind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            item=builtin_name,
        )
        self.write_project_driver_config(config, config_path)
        return config

    def get_project_driver_package_builtin(
        self,
        package_name: str,
        config_path: Path | None = None,
    ) -> list[str]:
        config = self.read_project_driver_config(config_path)
        return get_package_bound_items(
            cast("dict[str, Any]", config),
            package_name=package_name,
        )

    def unbind_project_driver_package(
        self,
        package_name: str,
        builtin_name: str | None = None,
        config_path: Path | None = None,
    ) -> DriverConfig:
        config = self.read_project_driver_config(config_path)
        changed = unbind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            items_key="builtin",
            item=builtin_name,
        )
        if not changed:
            return config
        self.write_project_driver_config(config, config_path)
        return config

    def effective_driver_builtin(self, builtin: list[str]) -> list[str]:
        """Normalize configured drivers into one primary driver plus optional mixins."""
        normalized = [item for item in builtin if item]
        if not normalized:
            return []

        capabilities = {
            item: self._driver_builtin_capabilities(item) for item in normalized
        }
        pure_drivers = [
            item
            for item in normalized
            if capabilities[item]["driver"] and not capabilities[item]["mixin"]
        ]
        if pure_drivers:
            primary = pure_drivers[-1]
            mixins = [
                item
                for item in normalized
                if item != primary and capabilities[item]["mixin"]
            ]
            return [primary, *mixins]

        hybrid = next(
            (item for item in normalized if capabilities[item]["driver"]),
            None,
        )
        if hybrid is not None:
            mixins = [
                item
                for item in normalized
                if item != hybrid and capabilities[item]["mixin"]
            ]
            return [hybrid, *mixins]

        return normalized

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        return load_toml_dict(
            config_path,
            logger=logger,
            missing_dependency_message=(
                "Skip loading apeiria.drivers.toml: tomllib/tomli is unavailable"
            ),
        )

    def _normalize_config(self, data: dict[str, Any]) -> DriverConfig:
        driver_config = data.get("drivers")
        if not isinstance(driver_config, dict):
            return {"builtin": [], "packages": {}}
        package_config = data.get("driver_packages")
        return {
            "builtin": normalize_string_list(driver_config.get("builtin")),
            "packages": normalize_package_item_map(package_config),
        }

    def _dump_config(self, config: DriverConfig) -> str:
        builtin = ", ".join(f'"{item}"' for item in config["builtin"])
        lines = [
            "[drivers]",
            f"builtin = [{builtin}]",
            "",
        ]
        if config["packages"]:
            lines.append("[driver_packages]")
            for package_name in sorted(config["packages"]):
                mapped = ", ".join(
                    f'"{item}"' for item in config["packages"][package_name]
                )
                lines.append(f'"{package_name}" = [{mapped}]')
            lines.append("")
        return "\n".join(lines)

    def _merge_driver_builtin(self, current: list[str], builtin_name: str) -> list[str]:
        combined = [item for item in current if item != builtin_name]
        combined.append(builtin_name)
        return self.effective_driver_builtin(combined)

    def _driver_builtin_capabilities(self, builtin_name: str) -> dict[str, bool]:
        module_name = builtin_name.strip().removeprefix("~")
        if not module_name:
            return {"driver": False, "mixin": False}

        try:
            from apeiria.environment.extension_project import (
                inject_plugin_site_packages,
            )

            inject_plugin_site_packages()
            module = importlib.import_module(f"nonebot.drivers.{module_name}")
        except ImportError:
            return {"driver": False, "mixin": False}

        return {
            "driver": hasattr(module, "Driver"),
            "mixin": hasattr(module, "Mixin"),
        }


driver_config_service = DriverConfigService()
