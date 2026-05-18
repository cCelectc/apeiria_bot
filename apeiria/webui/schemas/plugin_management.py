"""Plugin management Web UI schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PluginTogglePreviewResponse(BaseModel):
    module_name: str
    enabled: bool
    allowed: bool = True
    summary: str = ""
    blocked_reason: str | None = None
    requires_enable: list[str] = []
    requires_disable: list[str] = []
    protected_dependents: list[str] = []
    missing_dependencies: list[str] = []


class PluginToggleResponse(BaseModel):
    module_name: str
    enabled: bool
    affected_modules: list[str] = []


class PluginPolicyUpdateRequest(BaseModel):
    enabled: bool
    cascade: bool = False


class PluginPolicyStateResponse(BaseModel):
    enabled: bool


class PluginPolicyUpdateResponse(BaseModel):
    module_name: str
    policy: PluginPolicyStateResponse
    affected_modules: list[str] = []
    runtime_effect: str
    startup_effect: str
    restart_required: bool = True


class PluginManualInstallRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=512)
    module_name: str | None = Field(default=None, max_length=256)


class PluginInstallSource(BaseModel):
    kind: Literal["store_item", "requirement", "local_path"]
    value: str | None = Field(default=None, max_length=512)
    source_id: str | None = Field(default=None, max_length=128)
    item_id: str | None = Field(default=None, max_length=256)

    @classmethod
    def from_domain(cls, source: Any) -> "PluginInstallSource":
        return cls(
            kind=source.kind,
            value=source.value,
            source_id=source.source_id,
            item_id=source.item_id,
        )


class PluginInstallResolveRequest(BaseModel):
    source: PluginInstallSource


class PluginInstallCandidateItem(BaseModel):
    module_name: str
    kind: Literal["module", "directory"] = "module"
    confidence: Literal["high", "medium", "low"] = "medium"
    reason: str = ""
    already_registered: bool = False
    already_loaded: bool = False

    @classmethod
    def from_domain(cls, item: Any) -> "PluginInstallCandidateItem":
        return cls(
            module_name=item.module_name,
            kind=item.kind,
            confidence=item.confidence,
            reason=item.reason,
            already_registered=item.already_registered,
            already_loaded=item.already_loaded,
        )


class PluginInstallDefaultAction(BaseModel):
    kind: Literal[
        "install_package",
        "register_local_module",
        "register_local_directory",
    ]
    requirement: str | None = None
    module_name: str | None = None
    path: str | None = None

    @classmethod
    def from_domain(cls, action: Any) -> "PluginInstallDefaultAction":
        return cls(
            kind=action.kind,
            requirement=action.requirement,
            module_name=action.module_name,
            path=action.path,
        )


class PluginInstallResolveResponse(BaseModel):
    source: PluginInstallSource
    status: Literal["resolved", "ambiguous", "unresolved", "invalid", "installed"]
    candidates: list[PluginInstallCandidateItem] = []
    default_action: PluginInstallDefaultAction | None = None
    warnings: list[str] = []

    @classmethod
    def from_domain(cls, state: Any) -> "PluginInstallResolveResponse":
        return cls(
            source=PluginInstallSource.from_domain(state.source),
            status=state.status,
            candidates=[
                PluginInstallCandidateItem.from_domain(item)
                for item in state.candidates
            ],
            default_action=(
                PluginInstallDefaultAction.from_domain(state.default_action)
                if state.default_action is not None
                else None
            ),
            warnings=state.warnings,
        )


class PluginInstallConfirmRequest(BaseModel):
    source: PluginInstallSource
    action: PluginInstallDefaultAction


class PluginPackageUpdateRequest(BaseModel):
    package_name: str = Field(min_length=1, max_length=256)


class PluginUninstallRequest(BaseModel):
    remove_config: bool = False


def to_plugin_toggle_response(result: Any) -> PluginToggleResponse:
    return PluginToggleResponse(
        module_name=result.module_name,
        enabled=result.enabled,
        affected_modules=result.affected_modules,
    )


def to_plugin_policy_update_response(
    result: Any,
    *,
    was_loaded: bool | None = None,
) -> PluginPolicyUpdateResponse:
    enabled = bool(result.enabled)
    if was_loaded is None:
        runtime_effect = "execution_allowed" if enabled else "execution_blocked"
        restart_required = True
    elif enabled and was_loaded:
        runtime_effect = "execution_allowed"
        restart_required = False
    elif enabled and not was_loaded:
        runtime_effect = "requires_restart_to_load"
        restart_required = True
    else:
        runtime_effect = "execution_blocked" if was_loaded else "already_not_loaded"
        restart_required = was_loaded
    return PluginPolicyUpdateResponse(
        module_name=result.module_name,
        policy=PluginPolicyStateResponse(enabled=enabled),
        affected_modules=result.affected_modules,
        runtime_effect=runtime_effect,
        startup_effect=(
            "load_on_next_start" if enabled else "skip_loading_on_next_start"
        ),
        restart_required=restart_required,
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
