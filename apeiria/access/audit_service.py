"""Unified governance audit service."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from apeiria.access.audit import (
    AuditActor,
    AuditEvent,
    AuditEventKind,
    AuditOutcome,
)

AuditSink = Callable[[AuditEvent], None]


class AuditService:
    """Collect and fan out governance audit events."""

    def __init__(self, *, capacity: int = 500) -> None:
        self._buffer: deque[AuditEvent] = deque(maxlen=capacity)
        self._sinks: list[AuditSink] = []

    def record(  # noqa: PLR0913
        self,
        kind: AuditEventKind,
        *,
        actor: AuditActor | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        outcome: AuditOutcome = "succeeded",
        detail: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            kind=kind,
            occurred_at=datetime.now(timezone.utc),
            actor=actor,
            target_kind=target_kind,
            target_id=target_id,
            outcome=outcome,
            detail=detail,
            metadata=dict(metadata or {}),
        )
        self._buffer.append(event)
        self._fan_out(event)
        return event

    def _fan_out(self, event: AuditEvent) -> None:
        for sink in self._sinks:
            try:
                sink(event)
            except Exception:  # noqa: BLE001, PERF203
                continue

    def register_sink(self, sink: AuditSink) -> None:
        """Register a sink for newly recorded audit events."""

        self._sinks.append(sink)

    def snapshot(
        self,
        *,
        kind: AuditEventKind | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        """Return the most recent events, optionally filtered by kind."""

        items = list(self._buffer)
        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if limit is not None and limit >= 0:
            items = items[-limit:]
        return items

    def clear(self) -> None:
        self._buffer.clear()


audit_service = AuditService()
