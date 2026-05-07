"""AI diagnostics application entry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .model_connectivity import (
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from .readiness import (
    AIRuntimeReadinessProbe,
    AIRuntimeStatus,
    AIRuntimeStatusDiagnostics,
)
from .traces import TraceInspectionAdminMixin

if TYPE_CHECKING:
    from apeiria.app.ai.diagnostics.readiness import (
        AIModelSelector,
        RuntimeReadinessProbe,
    )
    from apeiria.app.ai.runtime.trace import TurnTraceRepository


class AIDiagnosticsEntry(TraceInspectionAdminMixin):
    """Application entry for AI read-only diagnostics."""

    def __init__(
        self,
        *,
        trace_repository: "TurnTraceRepository | None" = None,
        model_selector: "AIModelSelector | None" = None,
        runtime_readiness_probe: "RuntimeReadinessProbe | None" = None,
    ) -> None:
        super().__init__(trace_repository=trace_repository)
        self._runtime_status = AIRuntimeStatusDiagnostics(
            model_selector=model_selector,
            runtime_readiness_probe=runtime_readiness_probe,
        )

    async def get_runtime_status(self) -> AIRuntimeStatus:
        """Return read-only runtime readiness/status diagnostics."""

        return await self._runtime_status.get_status()


ai_diagnostics = AIDiagnosticsEntry()

__all__ = [
    "AIDiagnosticsEntry",
    "AIRuntimeReadinessProbe",
    "AIRuntimeStatus",
    "AIRuntimeStatusDiagnostics",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_diagnostics",
]
