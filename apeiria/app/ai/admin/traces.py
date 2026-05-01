"""Admin read model for compact AI runtime traces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.session_runtime.trace_store import turn_trace_repository

if TYPE_CHECKING:
    from apeiria.app.ai.session_runtime.trace_store import (
        TurnTraceRecord,
        TurnTraceRepository,
    )


class TraceInspectionAdminMixin:
    """Expose compact turn trace inspection for admin surfaces."""

    def __init__(
        self,
        *,
        trace_repository: "TurnTraceRepository | None" = None,
    ) -> None:
        self._trace_repository = trace_repository or turn_trace_repository

    async def list_turn_traces(  # noqa: PLR0913
        self,
        *,
        limit: int,
        trace_id: str | None = None,
        session_id: str | None = None,
        runtime_mode: str | None = None,
        terminal_status: str | None = None,
        commit_status: str | None = None,
    ) -> list["TurnTraceRecord"]:
        return self._trace_repository.list_traces(
            limit=limit,
            trace_id=trace_id,
            session_id=session_id,
            runtime_mode=runtime_mode,
            terminal_status=terminal_status,
            commit_status=commit_status,
        )

    async def get_turn_trace(self, *, trace_id: str) -> "TurnTraceRecord | None":
        return self._trace_repository.get_trace(trace_id=trace_id)


__all__ = ["TraceInspectionAdminMixin"]
