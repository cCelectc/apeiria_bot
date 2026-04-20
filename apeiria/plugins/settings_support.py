"""Declared config resolution and update validation for plugin settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.config import Config, Env
from pydantic import BaseModel

from apeiria.config.bot_config import BotConfig
from apeiria.plugins.metadata.registry import configs_from_model
from apeiria.plugins.metadata.resolver import resolve_config_namespace_contract
from apeiria.plugins.settings_capabilities import coerce_config_value

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig

_CORE_SETTINGS_EXCLUDED_KEYS = {
    "driver",
    "environment",
}
_STRIP = object()


class UnknownPluginSettingFieldError(ValueError):
    """Raised when an update references an undeclared config field."""

    def __init__(self, field_name: str) -> None:
        super().__init__(f"unknown field {field_name}")


@dataclass(frozen=True)
class PluginDeclaredConfig:
    module_name: str
    section: str
    legacy_flatten: bool
    config_source: str
    has_config_model: bool
    configs: list[RegisterConfig]


def get_plugin_declared_configs(module_name: str) -> PluginDeclaredConfig:
    """Resolve a plugin's declared config model and storage section."""
    resolved = resolve_config_namespace_contract(module_name)
    return PluginDeclaredConfig(
        module_name=module_name,
        section=resolved.namespace,
        legacy_flatten=resolved.legacy_flatten,
        config_source=resolved.source,
        has_config_model=resolved.has_config_model,
        configs=resolved.configs,
    )


def build_core_declared_configs() -> list[RegisterConfig]:
    """Build the editable core config field list."""
    merged: dict[str, RegisterConfig] = {}
    for model in (Env, Config, BotConfig):
        for config in configs_from_model(model):
            if config.key not in _CORE_SETTINGS_EXCLUDED_KEYS:
                merged[config.key] = config
    return list(merged.values())


def validate_and_coerce_updates(
    values: dict[str, object | None],
    clear: list[str],
    configs: list[RegisterConfig],
) -> dict[str, object | None]:
    """Validate update keys and coerce values from transport payloads."""
    allowed_fields = {config.key: config for config in configs}
    updates: dict[str, object | None] = {}
    for key, value in values.items():
        config = allowed_fields.get(key)
        if config is None:
            raise UnknownPluginSettingFieldError(key)
        coerced = coerce_config_value(config, value)
        stripped = _strip_default_value(config, coerced)
        updates[key] = None if stripped is _STRIP else stripped
    for key in clear:
        if key not in allowed_fields:
            raise UnknownPluginSettingFieldError(key)
        updates[key] = None
    return updates


def _strip_default_value(
    config: RegisterConfig,
    value: object | None,
) -> object | None:
    if value is None:
        return _STRIP

    if config.fields:
        return _strip_object_default_value(config, value)

    if config.type in {list, set}:
        return _strip_sequence_default_value(config, value)

    if config.type is dict:
        return _strip_mapping_default_value(config, value)

    return _STRIP if value == _normalized_default_value(config) else value


def _normalized_default_value(config: RegisterConfig) -> object | None:
    if isinstance(config.default, BaseModel):
        return config.default.model_dump(mode="python")
    return config.default


def _strip_object_default_value(
    config: RegisterConfig,
    value: object,
) -> object | None:
    default_value = _normalized_default_value(config)
    if not isinstance(value, dict):
        return _STRIP if value == default_value else value

    stripped_object: dict[str, object | None] = {}
    field_map = {field.key: field for field in config.fields}
    for key, item in value.items():
        field = field_map.get(key)
        if field is None:
            stripped_object[key] = item
            continue
        stripped_item = _strip_default_value(field, item)
        if stripped_item is _STRIP:
            continue
        stripped_object[key] = stripped_item
    return stripped_object or _STRIP


def _strip_sequence_default_value(
    config: RegisterConfig,
    value: object,
) -> object | None:
    default_value = _normalized_default_value(config)
    if not isinstance(value, list):
        return _STRIP if value == default_value else value
    if config.item_schema is None:
        return _STRIP if value == default_value else value

    stripped_list = [
        stripped_item
        for item in value
        if (stripped_item := _strip_default_value(config.item_schema, item))
        is not _STRIP
    ]
    return _STRIP if stripped_list == default_value else stripped_list


def _strip_mapping_default_value(
    config: RegisterConfig,
    value: object,
) -> object | None:
    default_value = _normalized_default_value(config)
    if not isinstance(value, dict):
        return _STRIP if value == default_value else value
    if config.value_schema is None:
        return _STRIP if value == default_value else value

    stripped_mapping = {
        key: stripped_item
        for key, item in value.items()
        if (stripped_item := _strip_default_value(config.value_schema, item))
        is not _STRIP
    }
    return _STRIP if stripped_mapping == default_value else stripped_mapping


__all__ = [
    "PluginDeclaredConfig",
    "UnknownPluginSettingFieldError",
    "build_core_declared_configs",
    "get_plugin_declared_configs",
    "validate_and_coerce_updates",
]
