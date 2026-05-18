"""Plugin catalog and read-side Web UI schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .plugin_config import PluginWorkspaceSettingsSummary  # noqa: TC001
from .plugin_management import PluginTogglePreviewResponse  # noqa: TC001

if TYPE_CHECKING:
    from apeiria.plugins.readme import PluginReadme
    from apeiria.plugins.settings_cleanup import (
        OrphanPluginConfigItem as DomainOrphanPluginConfigItem,
    )


class PluginItem(BaseModel):
    module_name: str
    kind: str = "plugin"
    access_mode: str = "default_allow"
    name: str | None
    description: str | None
    homepage: str | None = None
    source: str
    is_global_enabled: bool
    is_protected: bool = False
    protected_reason: str | None = None
    plugin_type: str = "normal"
    author: str | None = None
    version: str | None = None
    is_loaded: bool = True
    is_explicit: bool = False
    is_dependency: bool = False
    is_pending_uninstall: bool = False
    can_edit_config: bool = True
    can_view_readme: bool = False
    can_enable_disable: bool = False
    can_uninstall: bool = False
    can_package_update: bool = False
    child_plugins: list[str] = []
    required_plugins: list[str] = []
    dependent_plugins: list[str] = []
    installed_package: str | None = None
    installed_module_names: list[str] = []


class PluginUpdateCheckRequest(BaseModel):
    force_refresh: bool = False


class PluginUpdateCheckItem(BaseModel):
    module_name: str
    package_name: str
    current_version: str | None = None
    latest_version: str | None = None
    has_update: bool = False
    checked: bool = False
    error: str | None = None


class PluginWorkspaceResponse(BaseModel):
    plugin: PluginItem
    enable_preview: PluginTogglePreviewResponse | None = None
    disable_preview: PluginTogglePreviewResponse | None = None
    settings: PluginWorkspaceSettingsSummary | None = None
    readme_available: bool = False


class PluginReadmeResponse(BaseModel):
    module_name: str
    filename: str
    content: str


class OrphanPluginConfigItem(BaseModel):
    section: str
    module_name: str | None = None
    has_section: bool
    reason: str


class OrphanPluginConfigResponse(BaseModel):
    items: list[OrphanPluginConfigItem]


def to_orphan_plugin_config_response(
    items: list["DomainOrphanPluginConfigItem"],
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


def to_plugin_readme_response(state: "PluginReadme") -> PluginReadmeResponse:
    return PluginReadmeResponse(
        module_name=state.module_name,
        filename=state.filename,
        content=state.content,
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
