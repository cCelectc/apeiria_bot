"""AI diagnostics application entry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .model_connectivity import (
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from .traces import TraceInspectionAdminMixin

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.trace import TurnTraceRepository


class AIDiagnosticsEntry(TraceInspectionAdminMixin):
    """Application entry for AI read-only diagnostics."""

    def __init__(
        self,
        *,
        trace_repository: "TurnTraceRepository | None" = None,
    ) -> None:
        super().__init__(trace_repository=trace_repository)


ai_diagnostics = AIDiagnosticsEntry()

__all__ = [
    "AIDiagnosticsEntry",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_diagnostics",
]
