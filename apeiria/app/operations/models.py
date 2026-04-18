"""Operations-plane application models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

PackageOperationKind = Literal[
    "install",
    "update",
    "uninstall",
    "register",
    "unregister",
]
ResourceKind = Literal["plugin", "adapter", "driver", "package"]


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Current host environment facts needed by operations surfaces."""

    project_root: Path
    main_config_path: Path
    plugin_project_root: Path
    main_lock_exists: bool
    plugin_project_exists: bool
    plugin_lock_exists: bool
    project_config_exists: bool
    plugin_config_exists: bool
    adapter_config_exists: bool
    driver_config_exists: bool
    main_virtualenv_exists: bool
    uv_available: bool
    node_available: bool
    pnpm_available: bool
    npm_available: bool
    frontend_workspace_exists: bool
    frontend_dist_exists: bool
    frontend_build_is_built: bool
    frontend_build_is_stale: bool
    frontend_build_detail: str | None = None
    frontend_build_tool: str | None = None


@dataclass(frozen=True)
class EnvironmentRepairPlan:
    """Structured repair guidance for environment issues."""

    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FrontendBuildSnapshot:
    """Current Web UI frontend build status."""

    is_built: bool
    is_stale: bool
    can_build: bool
    build_tool: str | None
    detail: str | None


@dataclass(frozen=True)
class FrontendBuildRunResult(FrontendBuildSnapshot):
    """Frontend build result with merged logs."""

    logs: str = ""


@dataclass(frozen=True)
class FrontendBuildStreamEvent:
    """One streamed frontend build event."""

    event: str
    chunk: str = ""
    detail: str | None = None
    status: FrontendBuildSnapshot | None = None


@dataclass(frozen=True)
class HealthCheck:
    """One structured health check."""

    key: str
    ok: bool
    detail: str
    message: str = ""
    hint: str | None = None


@dataclass(frozen=True)
class HealthSnapshot:
    """Aggregated host health snapshot."""

    status: str
    project_root: Path
    checks: list[HealthCheck]
    environment: EnvironmentSnapshot


@dataclass(frozen=True)
class PackageOperationRequest:
    """One operations-plane package request."""

    resource_kind: ResourceKind
    operation: PackageOperationKind
    requirement: str
    binding_value: str | None = None
    extra_args: tuple[str, ...] = ()
    source: str | None = None
    actor: str | None = None


@dataclass(frozen=True)
class PackageOperationResult:
    """Result of one operations-plane package mutation."""

    resource_kind: ResourceKind
    operation: PackageOperationKind
    requirement: str
    binding_values: list[str] = field(default_factory=list)
    status: str = "succeeded"
    restart_required: bool = True
    detail: str | None = None

    @property
    def binding_value(self) -> str | None:
        """Return the primary binding when there is exactly one."""
        return self.binding_values[0] if self.binding_values else None
