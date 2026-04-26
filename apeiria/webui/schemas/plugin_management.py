"""Plugin management Web UI schemas."""

from __future__ import annotations

from typing import Any

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


class PluginManualInstallRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=512)
    module_name: str | None = Field(default=None, max_length=256)


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
