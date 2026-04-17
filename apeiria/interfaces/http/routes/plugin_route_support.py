"""Shared helpers for plugin HTTP routes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from apeiria.app.plugins import (
    AdapterConfigState,
    ConfigTextView,
    ConfigValidationReport,
    ConfigView,
    DriverConfigState,
    PluginConfigConflictError,
    PluginConfigState,
    PluginReadme,
    PluginSettingsNotConfigurableError,
)
from apeiria.app.plugins import (
    OrphanPluginConfigItem as DomainOrphanPluginConfigItem,
)
from apeiria.interfaces.http.schemas.models import (
    AdapterConfigItem,
    AdapterConfigResponse,
    DriverConfigItem,
    DriverConfigResponse,
    OrphanPluginConfigItem,
    OrphanPluginConfigResponse,
    PluginConfigDirItem,
    PluginConfigModuleItem,
    PluginConfigResponse,
    PluginItem,
    PluginRawSettingsResponse,
    PluginReadmeResponse,
    PluginSettingFieldItem,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginStoreTaskItem,
    PluginTogglePreviewResponse,
    PluginToggleResponse,
    PluginUpdateCheckItem,
)
from apeiria.shared.i18n import t


def to_orphan_plugin_config_response(
    items: list[DomainOrphanPluginConfigItem],
) -> OrphanPluginConfigResponse:
    return OrphanPluginConfigResponse(
        items=[
            OrphanPluginConfigItem(
                section=item.section,
                module_name=item.module_name,
                has_section=item.has_section,
                reason=item.reason,
            )
            for item in items
        ]
    )


def to_adapter_config_response(state: AdapterConfigState) -> AdapterConfigResponse:
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


def to_driver_config_response(state: DriverConfigState) -> DriverConfigResponse:
    return DriverConfigResponse(
        builtin=[
            DriverConfigItem(
                name=item.name,
                is_active=item.is_active,
            )
            for item in state.builtin
        ]
    )


def to_plugin_config_response(state: PluginConfigState) -> PluginConfigResponse:
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


def to_plugin_settings_response(state: ConfigView) -> PluginSettingsResponse:
    return PluginSettingsResponse(
        module_name=state.module_name,
        section=state.section,
        legacy_flatten=state.legacy_flatten,
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
                global_key=item.global_key,
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
    state: ConfigTextView,
) -> PluginRawSettingsResponse:
    return PluginRawSettingsResponse(
        module_name=state.module_name,
        section=state.section,
        text=state.text,
    )


def to_plugin_readme_response(state: PluginReadme) -> PluginReadmeResponse:
    return PluginReadmeResponse(
        module_name=state.module_name,
        filename=state.filename,
        content=state.content,
    )


def to_raw_validation_response(
    state: ConfigValidationReport,
) -> PluginSettingsRawValidationResponse:
    return PluginSettingsRawValidationResponse(
        valid=state.valid,
        message=state.message,
        line=state.line,
        column=state.column,
    )


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


def to_plugin_item_response(
    plugin: Any,
    *,
    can_package_update: bool,
) -> PluginItem:
    return PluginItem(
        module_name=plugin.descriptor.module_name,
        kind=plugin.governance_state.kind,
        access_mode=plugin.governance_state.access_mode,
        name=plugin.descriptor.name,
        description=plugin.descriptor.description,
        homepage=plugin.descriptor.homepage,
        source=plugin.descriptor.source,
        is_global_enabled=plugin.governance_state.is_global_enabled,
        is_protected=plugin.governance_state.is_protected,
        protected_reason=plugin.governance_state.protected_reason,
        plugin_type=plugin.descriptor.plugin_type,
        admin_level=plugin.descriptor.admin_level,
        author=plugin.descriptor.author,
        version=plugin.descriptor.version,
        is_loaded=plugin.runtime_state.is_loaded,
        is_explicit=plugin.governance_state.is_explicit,
        is_dependency=plugin.governance_state.is_dependency,
        is_pending_uninstall=plugin.runtime_state.is_pending_uninstall,
        can_edit_config=plugin.governance_state.can_edit_config,
        can_view_readme=plugin.governance_state.can_view_readme,
        can_enable_disable=plugin.governance_state.can_enable_disable,
        can_uninstall=plugin.governance_state.can_uninstall,
        can_package_update=can_package_update,
        child_plugins=plugin.child_plugin_modules,
        required_plugins=plugin.governance_state.required_plugins,
        dependent_plugins=plugin.governance_state.dependent_plugins,
        installed_package=plugin.package_binding.installed_package,
        installed_module_names=plugin.package_binding.installed_module_names,
    )


def to_plugin_update_check_item(item: Any) -> PluginUpdateCheckItem:
    return PluginUpdateCheckItem(
        module_name=item.module_name,
        package_name=item.package_name,
        current_version=item.current_version,
        latest_version=item.latest_version,
        has_update=item.has_update,
        checked=item.checked,
        error=item.error,
    )


def to_plugin_toggle_response(result: Any) -> PluginToggleResponse:
    return PluginToggleResponse(
        module_name=result.module_name,
        enabled=result.enabled,
        affected_modules=result.affected_modules,
    )


def to_plugin_toggle_preview_response(preview: Any) -> PluginTogglePreviewResponse:
    return PluginTogglePreviewResponse(
        module_name=preview.module_name,
        enabled=preview.enabled,
        allowed=preview.allowed,
        summary=preview.summary,
        blocked_reason=preview.blocked_reason,
        requires_enable=preview.requires_enable,
        requires_disable=preview.requires_disable,
        protected_dependents=preview.protected_dependents,
        missing_dependencies=preview.missing_dependencies,
    )


def to_plugin_store_task_item(task: Any) -> PluginStoreTaskItem:
    return PluginStoreTaskItem(
        task_id=task.task_id,
        title=task.title,
        status=task.status,
        logs=task.logs,
        error=task.error,
        result=task.result,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
