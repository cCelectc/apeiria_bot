"""Retained compatibility shims for removed Web UI security-audit storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

_EVENTS: list["WebUISecurityAuditEvent"] = []


@dataclass(frozen=True)
class WebUISecurityAuditEvent:
    """Compatibility event type for removed Web UI audit APIs."""

    event_type: str
    occurred_at: str
    actor_username: str | None = None
    target_username: str | None = None
    detail: str | None = None


def append_security_audit_event(
    _event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    _EVENTS.append(
        WebUISecurityAuditEvent(
            event_type=_event_type,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            actor_username=actor_username,
            target_username=target_username,
            detail=detail,
        )
    )
    _mirror_to_governance_audit(
        _event_type,
        actor_username=actor_username,
        target_username=target_username,
        detail=detail,
    )


def _mirror_to_governance_audit(
    event_type: str,
    *,
    actor_username: str | None,
    target_username: str | None,
    detail: str | None,
) -> None:
    """Forward compatible auth-related events into the unified governance stream."""
    try:
        from apeiria.access.audit import AuditActor
        from apeiria.access.audit_service import audit_service
    except Exception:  # noqa: BLE001
        return

    actor = (
        AuditActor(
            actor_kind="webui_account" if actor_username != "host" else "host_operator",
            actor_id=actor_username,
            display_name=actor_username,
        )
        if actor_username
        else None
    )
    try:
        audit_service.record(
            f"auth.{event_type}",  # type: ignore[arg-type]
            actor=actor,
            target_kind="webui_account" if target_username else None,
            target_id=target_username,
            detail=detail,
        )
    except Exception:  # noqa: BLE001
        return


def list_security_audit_events(limit: int = 20) -> list[WebUISecurityAuditEvent]:
    """Return recent in-process compatibility events."""
    return _EVENTS[-limit:][::-1]


def record_security_audit_event(
    event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    """Compatibility no-op that only mirrors to governance audit when possible."""
    append_security_audit_event(
        event_type,
        actor_username=actor_username,
        target_username=target_username,
        detail=detail,
    )


__all__ = [
    "WebUISecurityAuditEvent",
    "append_security_audit_event",
    "list_security_audit_events",
    "record_security_audit_event",
]
