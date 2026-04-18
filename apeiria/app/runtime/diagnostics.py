"""Unified runtime diagnostics recorder."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

RuntimeDiagnosticKind = Literal[
    "trace",
    "ingress",
    "permission.decision",
    "permission.denied",
    "permission.degradation",
    "handler.attributed",
    "handler.error",
    "send.observed",
    "warning",
    "degradation",
    "plugin.sync",
]


@dataclass(frozen=True)
class RuntimeDiagnostic:
    """One structured runtime observation fact."""

    kind: RuntimeDiagnosticKind
    source: str
    message: str
    created_at: datetime
    request_id: str | None = None
    plugin_module: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class RuntimeDiagnosticRecorder:
    """Collect runtime diagnostics into a bounded ring buffer."""

    def __init__(self, *, capacity: int = 1024) -> None:
        self._buffer: deque[RuntimeDiagnostic] = deque(maxlen=capacity)

    def record(  # noqa: PLR0913
        self,
        kind: RuntimeDiagnosticKind,
        *,
        source: str,
        message: str = "",
        request_id: str | None = None,
        plugin_module: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> RuntimeDiagnostic:
        diagnostic = RuntimeDiagnostic(
            kind=kind,
            source=source,
            message=message,
            created_at=datetime.now(timezone.utc),
            request_id=request_id,
            plugin_module=plugin_module,
            data=dict(data or {}),
        )
        self._buffer.append(diagnostic)
        return diagnostic

    def snapshot(
        self,
        *,
        request_id: str | None = None,
        kind: RuntimeDiagnosticKind | None = None,
        limit: int | None = None,
    ) -> list[RuntimeDiagnostic]:
        """Return the most recent diagnostics, optionally filtered."""

        items = list(self._buffer)
        if request_id is not None:
            items = [item for item in items if item.request_id == request_id]
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if limit is not None and limit >= 0:
            items = items[-limit:]
        return items

    def clear(self) -> None:
        self._buffer.clear()


runtime_diagnostic_recorder = RuntimeDiagnosticRecorder()
