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
from .usage import AIModelUsageTotals, UsageDiagnosticsAdminMixin

if TYPE_CHECKING:
    from apeiria.ai.token_usage import AIModelUsageRepository
    from apeiria.app.ai.diagnostics.readiness import (
        AIModelSelector,
        RuntimeReadinessProbe,
    )
    from apeiria.app.ai.runtime.trace import TurnTraceRepository


class AIDiagnosticsEntry(UsageDiagnosticsAdminMixin, TraceInspectionAdminMixin):
    """Application entry for AI read-only diagnostics."""

    def __init__(
        self,
        *,
        trace_repository: "TurnTraceRepository | None" = None,
        usage_repository: "AIModelUsageRepository | None" = None,
        model_selector: "AIModelSelector | None" = None,
        runtime_readiness_probe: "RuntimeReadinessProbe | None" = None,
    ) -> None:
        TraceInspectionAdminMixin.__init__(self, trace_repository=trace_repository)
        UsageDiagnosticsAdminMixin.__init__(self, usage_repository=usage_repository)
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
    "AIModelUsageTotals",
    "AIRuntimeReadinessProbe",
    "AIRuntimeStatus",
    "AIRuntimeStatusDiagnostics",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_diagnostics",
]
