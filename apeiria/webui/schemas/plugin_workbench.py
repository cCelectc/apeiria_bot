"""Plugin workbench Web UI schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from apeiria.webui.schemas.plugin_catalog import PluginItem, to_plugin_item_response

EffectivePluginState = Literal[
    "active",
    "execution_blocked",
    "disabled",
    "not_loaded",
    "pending_uninstall",
]


class PluginWorkbenchPolicyState(BaseModel):
    enabled: bool
    can_change: bool
    locked_reason: str | None = None


class PluginWorkbenchRuntimeState(BaseModel):
    loaded: bool
    execution_blocked: bool


class PluginWorkbenchStartupState(BaseModel):
    will_load: bool
    requires_restart_to_apply_fully: bool


class PluginWorkbenchCapabilities(BaseModel):
    can_edit_settings: bool
    can_view_readme: bool
    can_enable_disable: bool
    can_uninstall: bool
    can_update_package: bool


class PluginWorkbenchItem(PluginItem):
    display_name: str
    policy: PluginWorkbenchPolicyState
    runtime: PluginWorkbenchRuntimeState
    startup: PluginWorkbenchStartupState
    effective_state: EffectivePluginState
    capabilities: PluginWorkbenchCapabilities


class PluginWorkbenchSummary(BaseModel):
    total: int
    enabled: int
    disabled: int
    blocked: int
    not_loaded: int = 0
    pending_restart: int = 0
    protected: int = 0


class PluginWorkbenchTaskSummary(BaseModel):
    task_id: str
    title: str
    status: str
    operation: str | None = None
    resource_kind: str | None = None


class PluginWorkbenchMaintenance(BaseModel):
    orphan_config_count: int = 0
    active_package_task: PluginWorkbenchTaskSummary | None = None


class PluginWorkbenchResponse(BaseModel):
    plugins: list[PluginWorkbenchItem]
    summary: PluginWorkbenchSummary
    maintenance: PluginWorkbenchMaintenance = Field(
        default_factory=PluginWorkbenchMaintenance
    )


class PluginWorkbenchState(BaseModel):
    """Application-built workbench state before route-level serialization."""

    plugins: list[Any]
    orphan_config_count: int = 0
    active_package_task: Any | None = None


def to_plugin_workbench_response(state: Any) -> PluginWorkbenchResponse:
    rows = [
        _to_workbench_item(
            plugin,
            can_package_update=bool(can_package_update),
        )
        for plugin, can_package_update in state.plugin_rows
    ]
    return PluginWorkbenchResponse(
        plugins=rows,
        summary=_build_summary(rows),
        maintenance=PluginWorkbenchMaintenance(
            orphan_config_count=state.orphan_config_count,
            active_package_task=(
                PluginWorkbenchTaskSummary(
                    task_id=state.active_package_task.task_id,
                    title=state.active_package_task.title,
                    status=state.active_package_task.status,
                    operation=state.active_package_task.operation,
                    resource_kind=state.active_package_task.resource_kind,
                )
                if state.active_package_task is not None
                else None
            ),
        ),
    )


def _to_workbench_item(
    plugin: Any,
    *,
    can_package_update: bool,
) -> PluginWorkbenchItem:
    base = to_plugin_item_response(plugin, can_package_update=can_package_update)
    policy_enabled = plugin.governance_state.is_global_enabled
    runtime_loaded = plugin.runtime_state.is_loaded
    pending_uninstall = plugin.runtime_state.is_pending_uninstall
    policy_can_change = (
        plugin.governance_state.can_enable_disable
        and not plugin.governance_state.is_protected
        and not pending_uninstall
    )
    will_load = policy_enabled and not pending_uninstall
    execution_blocked = runtime_loaded and not policy_enabled
    requires_restart = runtime_loaded != will_load
    effective_state = _effective_state(
        loaded=runtime_loaded,
        enabled=policy_enabled,
        pending_uninstall=pending_uninstall,
    )
    return PluginWorkbenchItem(
        **base.model_dump(),
        display_name=base.name or base.module_name,
        policy=PluginWorkbenchPolicyState(
            enabled=policy_enabled,
            can_change=policy_can_change,
            locked_reason=plugin.governance_state.protected_reason,
        ),
        runtime=PluginWorkbenchRuntimeState(
            loaded=runtime_loaded,
            execution_blocked=execution_blocked,
        ),
        startup=PluginWorkbenchStartupState(
            will_load=will_load,
            requires_restart_to_apply_fully=requires_restart,
        ),
        effective_state=effective_state,
        capabilities=PluginWorkbenchCapabilities(
            can_edit_settings=plugin.governance_state.can_edit_config,
            can_view_readme=plugin.governance_state.can_view_readme,
            can_enable_disable=policy_can_change,
            can_uninstall=plugin.governance_state.can_uninstall,
            can_update_package=can_package_update,
        ),
    )


def _effective_state(
    *,
    loaded: bool,
    enabled: bool,
    pending_uninstall: bool,
) -> EffectivePluginState:
    if pending_uninstall:
        return "pending_uninstall"
    if loaded and enabled:
        return "active"
    if loaded and not enabled:
        return "execution_blocked"
    if not loaded and enabled:
        return "not_loaded"
    return "disabled"


def _build_summary(rows: list[PluginWorkbenchItem]) -> PluginWorkbenchSummary:
    return PluginWorkbenchSummary(
        total=len(rows),
        enabled=sum(1 for row in rows if row.policy.enabled),
        disabled=sum(1 for row in rows if not row.policy.enabled),
        blocked=sum(1 for row in rows if row.runtime.execution_blocked),
        not_loaded=sum(1 for row in rows if row.effective_state == "not_loaded"),
        pending_restart=sum(
            1 for row in rows if row.startup.requires_restart_to_apply_fully
        ),
        protected=sum(1 for row in rows if row.is_protected),
    )
