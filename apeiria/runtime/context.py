from __future__ import annotations

"""Runtime context primitives."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from apeiria.access.models import AccessPolicyRule
    from apeiria.app.plugins.management import PluginWorkbenchState
    from apeiria.app.system.management import (
        DashboardEventSnapshot,
        DashboardStatusSnapshot,
        WebUIBuildRunSnapshot,
        WebUIBuildStatusSnapshot,
    )
    from apeiria.app.system.project_update import (
        ProjectUpdatePlan,
        ProjectUpdatePlanRequest,
        ProjectUpdateStatus,
        ProjectUpdateTask,
    )
    from apeiria.plugins.models import PluginCatalogEntry
    from apeiria.runtime.control_plane import ApeiriaControlPlane


class RuntimeConfigEntry(Protocol):
    """Project configuration entry owned by the runtime kernel."""


class RuntimeEnvironmentEntry(Protocol):
    """Project environment entry owned by the runtime kernel."""

    @property
    def project_root(self) -> "Path": ...


class RuntimeDatabaseEntry(Protocol):
    """Database runtime entry owned by the runtime kernel."""

    def ensure_ready(self) -> None: ...


class RuntimeConversationEntry(Protocol):
    """Conversation entry owned by the runtime kernel."""


class RuntimeChatEntry(Protocol):
    """Web chat entry owned by the runtime kernel."""


class RuntimePluginGovernanceEntry(Protocol):
    """Plugin governance entry owned by the runtime kernel."""

    async def list_plugins(self) -> list["PluginCatalogEntry"]: ...


class RuntimePluginManagementEntry(Protocol):
    """Owner-facing plugin management entry available through control plane."""

    async def list_plugins(self) -> list["PluginCatalogEntry"]: ...

    async def build_plugin_workbench(
        self,
        *,
        plugins: list["PluginCatalogEntry"] | None = None,
        can_package_update: object | None = None,
    ) -> "PluginWorkbenchState": ...

    def can_package_update(self, plugin: "PluginCatalogEntry") -> bool: ...


class RuntimeAccessEntry(Protocol):
    """Access-policy entry owned by the runtime kernel."""

    async def list_access_rules(self) -> list["AccessPolicyRule"]: ...


class RuntimeSystemManagementEntry(Protocol):
    """Runtime-level system management entry exposed by the control plane."""

    async def get_status_snapshot(self) -> "DashboardStatusSnapshot": ...

    def get_recent_events(
        self,
        *,
        limit: int = 8,
    ) -> list["DashboardEventSnapshot"]: ...

    def get_web_ui_build_status(self) -> "WebUIBuildStatusSnapshot": ...

    async def rebuild_web_ui(self) -> "WebUIBuildRunSnapshot": ...

    def stream_web_ui_rebuild(self) -> "AsyncIterator[bytes]": ...

    def schedule_restart(self) -> None: ...


class RuntimeProjectUpdateEntry(Protocol):
    """Project self-update entry exposed by the control plane."""

    def inspect(self) -> "ProjectUpdateStatus": ...

    def refresh_remote_refs(self, *, force: bool = False) -> "ProjectUpdateStatus": ...

    def create_plan(
        self,
        request: "ProjectUpdatePlanRequest",
    ) -> "ProjectUpdatePlan": ...

    async def create_task(
        self,
        request: "ProjectUpdatePlanRequest",
    ) -> "ProjectUpdateTask": ...

    def get_task(self, task_id: str) -> "ProjectUpdateTask | None": ...


class RuntimeAISessionsEntry(Protocol):
    """AI session management entry exposed through the runtime AI handle."""

    async def list_managed_sessions(self, *, limit: int = 50) -> list[object]: ...

    async def get_managed_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> object | None: ...


class RuntimeAIEntry(Protocol):
    """AI application entry owned by the runtime kernel."""

    sessions: RuntimeAISessionsEntry


@dataclass(slots=True)
class ApeiriaRuntime:
    """Minimal runtime kernel composed from owned domain handles."""

    project_root: Path
    config: RuntimeConfigEntry
    environment: RuntimeEnvironmentEntry
    database: RuntimeDatabaseEntry
    conversation: RuntimeConversationEntry
    chat: RuntimeChatEntry
    plugins: RuntimePluginGovernanceEntry
    plugin_management: RuntimePluginManagementEntry
    access: RuntimeAccessEntry
    system: RuntimeSystemManagementEntry
    project_update: RuntimeProjectUpdateEntry
    ai: RuntimeAIEntry
    control_plane: ApeiriaControlPlane | None = field(default=None)


_RUNTIME_CONTEXT: dict[str, ApeiriaRuntime | None] = {"current": None}


def set_current_runtime(runtime: ApeiriaRuntime | None) -> None:
    _RUNTIME_CONTEXT["current"] = runtime


def get_current_runtime() -> ApeiriaRuntime | None:
    return _RUNTIME_CONTEXT["current"]
