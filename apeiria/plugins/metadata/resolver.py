from __future__ import annotations

import pkgutil
from dataclasses import dataclass
from pathlib import Path

import nonebot
from pydantic import BaseModel

from apeiria._framework_loader import (
    FRAMEWORK_PLUGIN_MODULES,
)
from apeiria.config import plugin_config_service, project_config_service
from apeiria.plugins.metadata.api import PluginExtraData, RegisterConfig
from apeiria.plugins.metadata.contracts import ConfigNamespaceContract
from apeiria.plugins.metadata.registry import (
    PluginConfigRegistration,
    RegisterPluginConfigOptions,
    configs_from_model,
    get_registered_plugin_config,
    register_plugin_config,
)
from apeiria.plugins.metadata.static_scan import (
    scan_plugin_config,
    scan_plugin_config_from_origin,
)
from apeiria.utils.project_context import current_project_root

read_project_plugin_module_map = project_config_service.read_project_plugin_module_map
read_pyproject_nonebot_config = project_config_service.read_pyproject_nonebot_config
read_project_plugin_config = plugin_config_service.read_project_plugin_config
_DEFAULT_CONFIG_ORDER = 99
_FIELD_SHAPE_DEFAULTS: dict[str, object] = {
    "default": None,
    "type": str,
    "choices": [],
    "item_type": None,
    "key_type": None,
    "allows_null": False,
    "item_schema": None,
    "key_schema": None,
    "value_schema": None,
}


@dataclass(frozen=True)
class PluginScanCandidate:
    module_name: str
    origin: Path | None = None


def _merge_declared_configs(
    base: list[RegisterConfig],
    enhancements: list[RegisterConfig],
) -> list[RegisterConfig]:
    if not base:
        return list(enhancements)
    if not enhancements:
        return list(base)

    merged = {config.key: config for config in base}
    for enhancement in enhancements:
        existing = merged.get(enhancement.key)
        if existing is None:
            continue
        merged[enhancement.key] = _merge_declared_config(existing, enhancement)
    return list(merged.values())


def _merge_declared_config(
    base: RegisterConfig,
    enhancement: RegisterConfig,
) -> RegisterConfig:
    structure_override = _has_structure_override(enhancement)
    return RegisterConfig(
        key=base.key,
        default=_merge_config_value(base, enhancement, "default"),
        help=enhancement.help or base.help,
        type=_merge_config_value(base, enhancement, "type"),
        choices=list(enhancement.choices or base.choices),
        choice_labels=dict(enhancement.choice_labels or base.choice_labels),
        item_type=_merge_config_value(base, enhancement, "item_type"),
        key_type=_merge_config_value(base, enhancement, "key_type"),
        allows_null=bool(_merge_config_value(base, enhancement, "allows_null")),
        fields=(
            list(enhancement.fields)
            if structure_override and enhancement.fields
            else _merge_declared_configs(base.fields, enhancement.fields)
        ),
        item_schema=(
            enhancement.item_schema
            if structure_override
            else _merge_nested_schema(base.item_schema, enhancement.item_schema)
        ),
        key_schema=(
            enhancement.key_schema
            if structure_override
            else _merge_nested_schema(base.key_schema, enhancement.key_schema)
        ),
        value_schema=(
            enhancement.value_schema
            if structure_override
            else _merge_nested_schema(base.value_schema, enhancement.value_schema)
        ),
        label=enhancement.label or base.label,
        order=(
            enhancement.order
            if enhancement.order != _DEFAULT_CONFIG_ORDER
            else base.order
        ),
        secret=enhancement.secret or base.secret,
    )


def _merge_nested_schema(
    base: RegisterConfig | None,
    enhancement: RegisterConfig | None,
) -> RegisterConfig | None:
    if base is None:
        return enhancement
    if enhancement is None:
        return base
    return _merge_declared_config(base, enhancement)


def _merge_config_value(
    base: RegisterConfig,
    enhancement: RegisterConfig,
    name: str,
) -> object:
    value = getattr(enhancement, name)
    if not _same_config_value(value, _FIELD_SHAPE_DEFAULTS[name]):
        return value
    return getattr(base, name)


def _has_structure_override(config: RegisterConfig) -> bool:
    for name in ("type", "item_type", "key_type", "item_schema", "value_schema"):
        if not _same_config_value(getattr(config, name), _FIELD_SHAPE_DEFAULTS[name]):
            return True
    return False


def _same_config_value(left: object, right: object) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left == right
    return left is right or left == right


def _project_root() -> Path:
    return current_project_root()


def _resolve_plugin_dir(path: str) -> Path:
    plugin_dir = Path(path).expanduser()
    if plugin_dir.is_absolute():
        return plugin_dir.resolve()
    return (_project_root() / plugin_dir).resolve()


def _discover_plugin_dir_modules(paths: list[str]) -> list[PluginScanCandidate]:
    discovered: dict[str, PluginScanCandidate] = {}
    for raw_path in paths:
        plugin_dir = _resolve_plugin_dir(raw_path)
        if not plugin_dir.is_dir():
            continue
        for module_info in pkgutil.iter_modules([str(plugin_dir)]):
            if module_info.name.startswith("_"):
                continue
            module_spec = module_info.module_finder.find_spec(module_info.name, None)
            if module_spec is None or not module_spec.origin:
                continue
            discovered.setdefault(
                module_info.name,
                PluginScanCandidate(
                    module_name=module_info.name,
                    origin=Path(module_spec.origin),
                ),
            )
    return sorted(discovered.values(), key=lambda item: item.module_name)


def _iter_explicit_plugin_modules(
    *,
    project_config_path: Path | None = None,
    plugin_config_path: Path | None = None,
    pyproject_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    config = read_project_plugin_config(plugin_config_path)
    pyproject_config = read_pyproject_nonebot_config(pyproject_path)
    persisted_module_map = read_project_plugin_module_map(project_config_path)
    pyproject_modules = pyproject_config["plugins"]
    pyproject_dirs = pyproject_config["plugin_dirs"]

    module_names = [
        *FRAMEWORK_PLUGIN_MODULES,
        *config["modules"],
        *persisted_module_map.values(),
        *pyproject_modules,
    ]
    plugin_dirs = [*config["dirs"], *pyproject_dirs]
    return module_names, plugin_dirs


def collect_plugin_config_candidates(
    *,
    project_config_path: Path | None = None,
    plugin_config_path: Path | None = None,
    pyproject_path: Path | None = None,
) -> list[PluginScanCandidate]:
    module_names, plugin_dirs = _iter_explicit_plugin_modules(
        project_config_path=project_config_path,
        plugin_config_path=plugin_config_path,
        pyproject_path=pyproject_path,
    )

    candidates: dict[str, PluginScanCandidate] = {}
    for module_name in module_names:
        if module_name:
            candidates.setdefault(module_name, PluginScanCandidate(module_name))

    for candidate in _discover_plugin_dir_modules(plugin_dirs):
        candidates.setdefault(candidate.module_name, candidate)

    return sorted(candidates.values(), key=lambda item: item.module_name)


def _resolved_from_registration(
    registration: PluginConfigRegistration,
) -> ConfigNamespaceContract:
    return ConfigNamespaceContract(
        namespace=registration.section,
        owner_kind="plugin",
        owner_id=registration.plugin_name,
        source=registration.source,
        has_config_model=bool(registration.configs),
        configs=list(registration.configs),
    )


def ensure_config_namespace_contract(
    candidate: PluginScanCandidate,
) -> ConfigNamespaceContract:
    plugin_name = candidate.module_name
    registration = get_registered_plugin_config(plugin_name)
    if registration is not None:
        return _resolved_from_registration(registration)

    scanned = (
        scan_plugin_config_from_origin(plugin_name, candidate.origin)
        if candidate.origin is not None
        else scan_plugin_config(plugin_name)
    )
    if scanned.is_apeiria_plugin or not scanned.has_config_model:
        return ConfigNamespaceContract(
            namespace=plugin_name.rsplit(".", maxsplit=1)[-1],
            owner_kind="plugin",
            owner_id=plugin_name,
            source="none",
            has_config_model=False,
            configs=[],
        )

    registration = register_plugin_config(
        plugin_name,
        options=RegisterPluginConfigOptions(
            section=scanned.section,
            configs=scanned.configs,
            source="static_scan",
        ),
    )
    return _resolved_from_registration(registration)


def resolve_config_namespace_contract(module_name: str) -> ConfigNamespaceContract:
    registration = get_registered_plugin_config(module_name)
    if registration is not None:
        return _resolved_from_registration(registration)

    plugin = next(
        (
            item
            for item in nonebot.get_loaded_plugins()
            if item.module_name == module_name
        ),
        None,
    )
    if plugin and plugin.metadata:
        config_model = getattr(plugin.metadata, "config", None)
        if isinstance(config_model, type) and issubclass(config_model, BaseModel):
            extra = (
                PluginExtraData.from_extra(plugin.metadata.extra)
                if plugin.metadata.extra
                else None
            )
            configs = configs_from_model(config_model)
            if extra is not None:
                configs = _merge_declared_configs(configs, extra.configs)
            return ConfigNamespaceContract(
                namespace=module_name.rsplit(".", maxsplit=1)[-1],
                owner_kind="plugin",
                owner_id=module_name,
                source="plugin_metadata",
                has_config_model=True,
                configs=configs,
            )

    if plugin and plugin.metadata and plugin.metadata.extra:
        extra = PluginExtraData.from_extra(plugin.metadata.extra)
        if extra is not None:
            return ConfigNamespaceContract(
                namespace=module_name.rsplit(".", maxsplit=1)[-1],
                owner_kind="plugin",
                owner_id=module_name,
                source="plugin_metadata",
                has_config_model=bool(extra.configs),
                configs=extra.configs,
            )

    return ensure_config_namespace_contract(PluginScanCandidate(module_name))
