"""Support for building plugin and core settings view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.config import project_config_service
from apeiria.plugins.settings_capabilities import (
    format_type_name,
    get_field_capability,
    normalize_choice_items_for_response,
    normalize_value_for_response,
)
from apeiria.plugins.settings_support import build_core_declared_configs

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig
    from apeiria.plugins.settings import (
        ConfigFieldView,
    )
    from apeiria.plugins.settings_support import PluginDeclaredConfig


@dataclass(frozen=True)
class FieldValueState:
    base_value: object | None
    current_value: object | None
    local_value: object | None
    value_source: str
    has_local_override: bool = False


@dataclass(frozen=True)
class PluginFieldContext:
    plugin_config: dict[str, object]
    env_config: dict[str, object]


def build_plugin_setting_fields(
    declared: "PluginDeclaredConfig",
) -> list["ConfigFieldView"]:
    """Combine plugin declarations with current effective values."""
    ctx = PluginFieldContext(
        plugin_config=project_config_service.read_project_plugin_config(
            declared.section
        ),
        env_config=project_config_service.read_env_config(),
    )
    return [
        build_setting_field_item(
            config,
            build_plugin_field_state(config, ctx),
        )
        for config in declared.configs
    ]


def build_core_setting_fields() -> list["ConfigFieldView"]:
    """Build the editable core settings field list with current values."""
    effective_config = project_config_service.read_project_config()
    env_config = project_config_service.read_env_config()
    section_config = project_config_service.read_project_nonebot_section_config()
    return [
        build_setting_field_item(
            config,
            build_core_field_state(
                config,
                env_config,
                effective_config,
                section_config,
            ),
        )
        for config in build_core_declared_configs()
    ]


def build_plugin_field_state(
    config: "RegisterConfig",
    ctx: PluginFieldContext,
) -> FieldValueState:
    """Build field state for one plugin config item."""
    current_value: object | None = config.default
    base_value: object | None = config.default
    local_value: object | None = None
    value_source = "default"
    if config.key in ctx.env_config and ctx.env_config[config.key] != config.default:
        base_value = ctx.env_config[config.key]
        current_value = base_value
        value_source = "env"
    if config.key in ctx.plugin_config:
        local_value = ctx.plugin_config[config.key]
        current_value = ctx.plugin_config[config.key]
        value_source = "plugin_section"

    return FieldValueState(
        base_value=base_value,
        current_value=current_value,
        local_value=local_value,
        value_source=value_source,
        has_local_override=config.key in ctx.plugin_config,
    )


def build_core_field_state(
    config: "RegisterConfig",
    env_config: dict[str, object],
    effective_config: dict[str, object],
    section_config: dict[str, object],
) -> FieldValueState:
    """Build field state for one core config item."""
    current_value: object | None = config.default
    base_value: object | None = config.default
    local_value: object | None = None
    value_source = "default"

    if config.key in env_config and env_config[config.key] != config.default:
        base_value = env_config[config.key]
        current_value = base_value
        value_source = "env"
    if config.key in section_config:
        local_value = section_config[config.key]
        current_value = section_config[config.key]
        value_source = "plugin_section"
    elif (
        config.key in effective_config
        and effective_config[config.key] != config.default
    ):
        base_value = effective_config[config.key]
        current_value = base_value
        value_source = "env"

    return FieldValueState(
        base_value=base_value,
        current_value=current_value,
        local_value=local_value,
        value_source=value_source,
        has_local_override=config.key in section_config,
    )


def build_setting_field_item(
    config: "RegisterConfig",
    state: FieldValueState,
) -> "ConfigFieldView":
    """Map one config declaration plus value state into UI-facing field state."""
    from apeiria.plugins.settings import ConfigFieldView

    capability = get_field_capability(config)
    return ConfigFieldView(
        key=config.key,
        label=config.label or config.key,
        type=format_type_name(config.type) or "unknown",
        editor=capability.editor,
        item_type=format_type_name(config.item_type),
        key_type=format_type_name(config.key_type),
        schema=build_setting_schema(config),
        default=normalize_value_for_response(config, config.default),
        help=config.help,
        choices=normalize_choice_items_for_response(config),
        base_value=normalize_value_for_response(config, state.base_value),
        current_value=normalize_value_for_response(config, state.current_value),
        local_value=normalize_value_for_response(config, state.local_value),
        value_source=state.value_source,
        has_local_override=state.has_local_override,
        allows_null=config.allows_null,
        editable=capability.editable,
        type_category=capability.category,
        order=config.order,
        secret=config.secret,
    )


def build_setting_schema(config: "RegisterConfig") -> dict[str, object]:
    return {
        "type": format_type_name(config.type) or "unknown",
        "item_type": format_type_name(config.item_type),
        "key_type": format_type_name(config.key_type),
        "choices": normalize_choice_items_for_response(config),
        "allows_null": config.allows_null,
        "fields": [
            {
                "key": field.key,
                "label": field.label or field.key,
                "help": field.help,
                "default": normalize_value_for_response(field, field.default),
                "schema": build_setting_schema(field),
            }
            for field in config.fields
        ],
        "item_schema": (
            {
                "key": config.item_schema.key,
                "label": config.item_schema.label or config.item_schema.key,
                "help": config.item_schema.help,
                "default": normalize_value_for_response(
                    config.item_schema,
                    config.item_schema.default,
                ),
                "schema": build_setting_schema(config.item_schema),
            }
            if config.item_schema is not None
            else None
        ),
        "key_schema": (
            {
                "key": config.key_schema.key,
                "label": config.key_schema.label or config.key_schema.key,
                "help": config.key_schema.help,
                "default": normalize_value_for_response(
                    config.key_schema,
                    config.key_schema.default,
                ),
                "schema": build_setting_schema(config.key_schema),
            }
            if config.key_schema is not None
            else None
        ),
        "value_schema": (
            {
                "key": config.value_schema.key,
                "label": config.value_schema.label or config.value_schema.key,
                "help": config.value_schema.help,
                "default": normalize_value_for_response(
                    config.value_schema,
                    config.value_schema.default,
                ),
                "schema": build_setting_schema(config.value_schema),
            }
            if config.value_schema is not None
            else None
        ),
    }


__all__ = [
    "FieldValueState",
    "PluginFieldContext",
    "build_core_field_state",
    "build_core_setting_fields",
    "build_plugin_field_state",
    "build_plugin_setting_fields",
    "build_setting_field_item",
]
