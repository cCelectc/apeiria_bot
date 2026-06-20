from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, cast

import nonebot
from nonebot.log import logger
from nonebot.utils import resolve_dot_notation

from apeiria.config.package_config import (
    add_unique_sorted_item,
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


class AdapterConfig(TypedDict):
    modules: list[str]
    packages: dict[str, list[str]]


class AdapterConfigService:
    """Manage project adapter registration and package bindings."""

    def _project_root(self) -> Path:
        return current_project_root()

    def default_config_path(self) -> Path:
        return self._project_root() / "apeiria.adapters.toml"

    def read_project_adapter_config(
        self,
        config_path: Path | None = None,
    ) -> AdapterConfig:
        target = config_path or self.default_config_path()
        return self._normalize_config(self._load_config(target))

    def write_project_adapter_config(
        self,
        config: AdapterConfig,
        config_path: Path | None = None,
    ) -> Path:
        target = config_path or self.default_config_path()
        atomic_write_text(target, self._dump_config(config))
        return target

    def ensure_project_adapter_config(self, config_path: Path | None = None) -> Path:
        target = config_path or self.default_config_path()
        if not target.exists():
            self.write_project_adapter_config({"modules": [], "packages": {}}, target)
        return target

    def add_project_adapter_module(
        self,
        module_name: str,
        config_path: Path | None = None,
    ) -> AdapterConfig:
        config = self.read_project_adapter_config(config_path)
        if add_unique_sorted_item(config["modules"], module_name):
            self.write_project_adapter_config(config, config_path)
        return config

    def remove_project_adapter_module(
        self,
        module_name: str,
        config_path: Path | None = None,
    ) -> AdapterConfig:
        config = self.read_project_adapter_config(config_path)
        remove_item_from_config_packages(
            cast("dict[str, Any]", config),
            items_key="modules",
            item=module_name,
        )
        self.write_project_adapter_config(config, config_path)
        return config

    def load_project_adapters(
        self,
        driver: object,
        config_path: Path | None = None,
    ) -> None:
        """Register configured adapters against the active NoneBot driver.

        Already-registered adapter classes are skipped so repeated bootstrap
        passes do not duplicate registration or fail on adapter conflicts.
        """
        config = self.read_project_adapter_config(config_path)
        register = getattr(driver, "register_adapter", None)
        if not callable(register):
            logger.warning(
                "Skip loading apeiria.adapters.toml: driver has no register_adapter"
            )
            return

        for module_name in config["modules"]:
            try:
                adapter_cls = resolve_dot_notation(module_name, "Adapter")
            except (ImportError, AttributeError, ValueError) as exc:
                logger.warning("Skip adapter {}: {}", module_name, exc)
                continue

            if self._is_adapter_registered(adapter_cls):
                logger.debug("Skip adapter %s: already registered", module_name)
                continue

            register(adapter_cls)

    def bind_project_adapter_package(
        self,
        package_name: str,
        module_name: str,
        config_path: Path | None = None,
    ) -> AdapterConfig:
        config = self.add_project_adapter_module(module_name, config_path)
        bind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            item=module_name,
        )
        self.write_project_adapter_config(config, config_path)
        return config

    def get_project_adapter_package_modules(
        self,
        package_name: str,
        config_path: Path | None = None,
    ) -> list[str]:
        config = self.read_project_adapter_config(config_path)
        return get_package_bound_items(
            cast("dict[str, Any]", config),
            package_name=package_name,
        )

    def unbind_project_adapter_package(
        self,
        package_name: str,
        module_name: str | None = None,
        config_path: Path | None = None,
    ) -> AdapterConfig:
        config = self.read_project_adapter_config(config_path)
        changed = unbind_package_item(
            cast("dict[str, Any]", config),
            package_name=package_name,
            items_key="modules",
            item=module_name,
        )
        if not changed:
            return config
        self.write_project_adapter_config(config, config_path)
        return config

    def _load_config(self, config_path: Path) -> dict[str, Any]:
        return load_toml_dict(
            config_path,
            logger=logger,
            missing_dependency_message=(
                "Skip loading apeiria.adapters.toml: tomllib/tomli is unavailable"
            ),
        )

    def _normalize_config(self, data: dict[str, Any]) -> AdapterConfig:
        adapter_config = data.get("adapters")
        if not isinstance(adapter_config, dict):
            return {"modules": [], "packages": {}}
        package_config = data.get("adapter_packages")
        return {
            "modules": normalize_string_list(adapter_config.get("modules")),
            "packages": normalize_package_item_map(package_config),
        }

    def _dump_config(self, config: AdapterConfig) -> str:
        modules = ", ".join(f'"{module}"' for module in config["modules"])
        lines = [
            "[adapters]",
            f"modules = [{modules}]",
            "",
        ]
        if config["packages"]:
            lines.append("[adapter_packages]")
            for package_name in sorted(config["packages"]):
                package_modules = config["packages"][package_name]
                mapped = ", ".join(f'"{module}"' for module in package_modules)
                lines.append(f'"{package_name}" = [{mapped}]')
            lines.append("")
        return "\n".join(lines)

    def _is_adapter_registered(self, adapter_cls: type[object]) -> bool:
        adapters = nonebot.get_adapters()
        return any(
            registered is adapter_cls
            or (
                getattr(registered, "__module__", None) == adapter_cls.__module__
                and getattr(registered, "__name__", None) == adapter_cls.__name__
            )
            for registered in adapters.values()
        )


adapter_config_service = AdapterConfigService()
