"""Plugin configuration Web UI schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from apeiria.i18n import t
from apeiria.plugins import (
    PluginConfigConflictError,
    PluginSettingsNotConfigurableError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.plugins import (
        AdapterConfigState,
        ConfigTextView,
        ConfigValidationReport,
        ConfigView,
        DriverConfigState,
        PluginConfigState,
    )

_ResultT = TypeVar("_ResultT")


class PluginWorkspaceSettingsSummary(BaseModel):
    module_name: str
    section: str
    config_source: str
    has_config_model: bool
    field_count: int


class PluginConfigResponse(BaseModel):
    modules: list["PluginConfigModuleItem"]
    dirs: list["PluginConfigDirItem"]


class PluginSettingFieldItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    type: str
    editor: str = "readonly"
    item_type: str | None = None
    key_type: str | None = None
    schema_: object | None = Field(default=None, alias="schema")
    default: object | None
    help: str
    choices: list[object] = []
    base_value: object | None = None
    current_value: object | None = None
    local_value: object | None = None
    value_source: str = "default"
    has_local_override: bool = False
    allows_null: bool = False
    editable: bool = False
    type_category: str = "unsupported"
    order: int = 99
    secret: bool = False


class PluginSettingsResponse(BaseModel):
    module_name: str
    section: str
    config_source: str = "none"
    has_config_model: bool = False
    fields: list[PluginSettingFieldItem]


class PluginRawSettingsResponse(BaseModel):
    module_name: str
    section: str
    text: str


class PluginSettingsUpdateRequest(BaseModel):
    values: dict[str, object | None]
    clear: list[str] = []


class PluginSettingsRawUpdateRequest(BaseModel):
    text: str


class PluginSettingsRawValidationResponse(BaseModel):
    valid: bool
    message: str | None = None
    line: int | None = None
    column: int | None = None


class PluginConfigRequest(BaseModel):
    modules: list[str]
    dirs: list[str]


class AdapterConfigItem(BaseModel):
    name: str
    is_loaded: bool
    is_importable: bool


class AdapterConfigResponse(BaseModel):
    modules: list[AdapterConfigItem]


class AdapterConfigRequest(BaseModel):
    modules: list[str]


class PluginConfigModuleItem(BaseModel):
    name: str
    is_loaded: bool
    is_importable: bool


class PluginConfigDirItem(BaseModel):
    path: str
    exists: bool
    is_loaded: bool


class DriverConfigItem(BaseModel):
    name: str
    is_active: bool


class DriverConfigResponse(BaseModel):
    builtin: list[DriverConfigItem]


class DriverConfigRequest(BaseModel):
    builtin: list[str]


def raise_settings_error(exc: Exception) -> None:
    if isinstance(exc, PluginConfigConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PluginSettingsNotConfigurableError):
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_configurable"),
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def run_settings_action(
    action: "Callable[..., _ResultT]",
    /,
    *args: object,
    **kwargs: object,
) -> _ResultT:
    try:
        return action(*args, **kwargs)
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc


def to_adapter_config_response(state: "AdapterConfigState") -> AdapterConfigResponse:
    return AdapterConfigResponse(
        modules=[
            AdapterConfigItem(
                name=item.name,
                is_loaded=item.is_loaded,
                is_importable=item.is_importable,
            )
            for item in state.modules
        ]
    )


def to_driver_config_response(state: "DriverConfigState") -> DriverConfigResponse:
    return DriverConfigResponse(
        builtin=[
            DriverConfigItem(
                name=item.name,
                is_active=item.is_active,
            )
            for item in state.builtin
        ]
    )


def to_plugin_config_response(state: "PluginConfigState") -> PluginConfigResponse:
    return PluginConfigResponse(
        modules=[
            PluginConfigModuleItem(
                name=item.name,
                is_loaded=item.is_loaded,
                is_importable=item.is_importable,
            )
            for item in state.modules
        ],
        dirs=[
            PluginConfigDirItem(
                path=item.path,
                exists=item.exists,
                is_loaded=item.is_loaded,
            )
            for item in state.dirs
        ],
    )


def to_plugin_settings_response(state: "ConfigView") -> PluginSettingsResponse:
    return PluginSettingsResponse(
        module_name=state.module_name,
        section=state.section,
        config_source=state.config_source,
        has_config_model=state.has_config_model,
        fields=[
            PluginSettingFieldItem(
                key=item.key,
                label=item.label,
                type=item.type,
                editor=item.editor,
                item_type=item.item_type,
                key_type=item.key_type,
                schema=item.schema,
                default=item.default,
                help=item.help,
                choices=list(item.choices),
                base_value=item.base_value,
                current_value=item.current_value,
                local_value=item.local_value,
                value_source=item.value_source,
                has_local_override=item.has_local_override,
                allows_null=item.allows_null,
                editable=item.editable,
                type_category=item.type_category,
                order=item.order,
                secret=item.secret,
            )
            for item in state.fields
        ],
    )


def to_plugin_raw_settings_response(
    state: "ConfigTextView",
) -> PluginRawSettingsResponse:
    return PluginRawSettingsResponse(
        module_name=state.module_name,
        section=state.section,
        text=state.text,
    )


def to_raw_validation_response(
    state: "ConfigValidationReport",
) -> PluginSettingsRawValidationResponse:
    return PluginSettingsRawValidationResponse(
        valid=state.valid,
        message=state.message,
        line=state.line,
        column=state.column,
    )


def to_plugin_workspace_settings_summary(
    state: "ConfigView",
) -> PluginWorkspaceSettingsSummary:
    return PluginWorkspaceSettingsSummary(
        module_name=state.module_name,
        section=state.section,
        config_source=state.config_source,
        has_config_model=state.has_config_model,
        field_count=len(state.fields),
    )
