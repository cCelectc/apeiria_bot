"""Runtime control plane primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.system.management import (
    DashboardStatusSnapshot,
    system_management_service,
)

if TYPE_CHECKING:
    from apeiria.runtime.context import ApeiriaRuntime


class ApeiriaControlPlane:
    """Read-side runtime control plane."""

    def __init__(self, runtime: ApeiriaRuntime) -> None:
        self._runtime = runtime

    async def list_plugins(self) -> list[Any]:
        return await self._runtime.plugins.list_plugins()

    async def get_dashboard_status(self) -> DashboardStatusSnapshot:
        return await system_management_service.get_status_snapshot()
