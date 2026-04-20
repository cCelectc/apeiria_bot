from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from apeiria.plugins.metadata.declarations import (
    register_config_from_runtime_annotation,
)

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig

ModelT = TypeVar("ModelT", bound=BaseModel)


class PluginConfigConflictError(ValueError):
    """Raised when plugin config registrations produce ambiguous global keys."""


@dataclass
class PluginConfigRegistration:
    plugin_name: str
    section: str
    configs: list[RegisterConfig]
    legacy_flatten: bool = False
    key_map: dict[str, str] = field(default_factory=dict)
    source: str = "manual"


@dataclass(frozen=True)
class RegisterPluginConfigOptions:
    section: str | None = None
    model: type[BaseModel] | None = None
    configs: list[RegisterConfig] | None = None
    legacy_flatten: bool = False
    key_map: dict[str, str] = field(default_factory=dict)
    source: str = "manual"


_REGISTRY: dict[str, PluginConfigRegistration] = {}


def _name_candidates(name: str) -> tuple[str, ...]:
    stripped = name.strip()
    if not stripped:
        return ()

    candidates = [stripped]
    underscored = stripped.replace("-", "_")
    if underscored not in candidates:
        candidates.append(underscored)
    dashed = stripped.replace("_", "-")
    if dashed not in candidates:
        candidates.append(dashed)
    return tuple(candidates)


def _model_to_configs(model: type[ModelT]) -> list[RegisterConfig]:
    result: list[RegisterConfig] = []
    for key, field_info in model.model_fields.items():
        default = (
            None
            if field_info.is_required()
            else field_info.get_default(call_default_factory=True)
        )
        result.append(
            register_config_from_runtime_annotation(
                key=key,
                annotation=field_info.annotation,
                default=default,
                help_text=field_info.description or "",
            )
        )
    return result


def configs_from_model(model: type[ModelT]) -> list[RegisterConfig]:
    return _model_to_configs(model)


def _default_section(plugin_name: str) -> str:
    return plugin_name.rsplit(".", maxsplit=1)[-1]


def _iter_legacy_global_keys(
    registration: PluginConfigRegistration,
) -> list[tuple[str, str]]:
    if not registration.legacy_flatten:
        return []
    return [
        (config.key, registration.key_map.get(config.key, config.key))
        for config in registration.configs
    ]


def _validate_registration_conflicts(
    registration: PluginConfigRegistration,
) -> None:
    existing_global_keys = {
        global_key: (registered.plugin_name, source_key)
        for registered in iter_registered_plugin_configs()
        if registered.plugin_name != registration.plugin_name
        for source_key, global_key in _iter_legacy_global_keys(registered)
    }
    local_seen: dict[str, str] = {}

    for source_key, global_key in _iter_legacy_global_keys(registration):
        local_owner = local_seen.get(global_key)
        if local_owner is not None and local_owner != source_key:
            msg = (
                f"plugin {registration.plugin_name} maps both {local_owner} and "
                f"{source_key} to legacy key {global_key}"
            )
            raise PluginConfigConflictError(msg)

        local_seen[global_key] = source_key
        conflict = existing_global_keys.get(global_key)
        if conflict is None:
            continue
        conflict_plugin, conflict_key = conflict
        msg = (
            f"legacy config key conflict for {global_key}: "
            f"{registration.plugin_name}.{source_key} conflicts with "
            f"{conflict_plugin}.{conflict_key}"
        )
        raise PluginConfigConflictError(msg)


def register_plugin_config(
    plugin_name: str,
    *,
    options: RegisterPluginConfigOptions | None = None,
) -> PluginConfigRegistration:
    resolved = options or RegisterPluginConfigOptions()
    declared_configs = resolved.configs or (
        _model_to_configs(resolved.model) if resolved.model else []
    )
    registration = PluginConfigRegistration(
        plugin_name=plugin_name,
        section=resolved.section or _default_section(plugin_name),
        configs=list(declared_configs),
        legacy_flatten=resolved.legacy_flatten,
        key_map=dict(resolved.key_map),
        source=resolved.source,
    )
    _validate_registration_conflicts(registration)
    for candidate in _name_candidates(plugin_name):
        _REGISTRY[candidate] = registration
    return registration


def get_registered_plugin_config(
    plugin_name: str,
) -> PluginConfigRegistration | None:
    for candidate in _name_candidates(plugin_name):
        registration = _REGISTRY.get(candidate)
        if registration is not None:
            return registration
    return None


def iter_registered_plugin_configs() -> list[PluginConfigRegistration]:
    unique: dict[str, PluginConfigRegistration] = {}
    for registration in _REGISTRY.values():
        unique[registration.plugin_name] = registration
    return list(unique.values())


def _read_plugin_table(data: dict[str, Any], section: str) -> dict[str, Any]:
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return {}

    for candidate in _name_candidates(section):
        plugin_config = plugins.get(candidate)
        if isinstance(plugin_config, dict):
            return dict(plugin_config)
    return {}


def build_legacy_nonebot_overrides(data: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for registration in iter_registered_plugin_configs():
        if not registration.legacy_flatten:
            continue
        plugin_data = _read_plugin_table(data, registration.section)
        for config in registration.configs:
            if config.key not in plugin_data:
                continue
            global_key = registration.key_map.get(config.key, config.key)
            overrides[global_key] = plugin_data[config.key]
    return overrides
