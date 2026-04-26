"""Web UI security audit storage and forwarding."""

from __future__ import annotations

from dataclasses import dataclass

from apeiria.access.webui_auth.store import auth_store, iso_now, persist_raw


@dataclass(frozen=True)
class WebUISecurityAuditEvent:
    """Stored security audit event."""

    event_type: str
    occurred_at: str
    actor_username: str | None = None
    target_username: str | None = None
    detail: str | None = None


def append_security_audit_event(
    event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    current_events = [
        item for item in auth_store.get("audit_events", []) if isinstance(item, dict)
    ]
    current_events.append(
        {
            "event_type": event_type,
            "occurred_at": iso_now(),
            "actor_username": actor_username,
            "target_username": target_username,
            "detail": detail,
        }
    )
    auth_store["audit_events"] = current_events[-100:]
    _mirror_to_governance_audit(
        event_type,
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
    """Forward webui audit events into the unified governance audit stream."""
    try:
        from apeiria.access.audit import AuditActor
        from apeiria.access.audit_service import audit_service
    except Exception:  # noqa: BLE001
        return

    kind = f"auth.{event_type}"
    allowed = {
        "auth.login_succeeded",
        "auth.login_failed",
        "auth.password_changed",
        "auth.sessions_revoked",
        "auth.account_created",
        "auth.account_disabled",
        "auth.account_enabled",
        "auth.account_deleted",
        "auth.registration_code_created",
        "auth.registration_code_revoked",
        "auth.registration_code_used",
        "auth.owner_account_recovered",
    }
    if kind not in allowed:
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
            kind,  # type: ignore[arg-type]
            actor=actor,
            target_kind="webui_account" if target_username else None,
            target_id=target_username,
            detail=detail,
        )
    except Exception:  # noqa: BLE001
        return


def list_security_audit_events(limit: int = 20) -> list[WebUISecurityAuditEvent]:
    """List recent security audit events."""
    items = [
        WebUISecurityAuditEvent(
            event_type=str(item.get("event_type") or "unknown"),
            occurred_at=str(item.get("occurred_at") or ""),
            actor_username=(
                str(item.get("actor_username"))
                if item.get("actor_username") is not None
                else None
            ),
            target_username=(
                str(item.get("target_username"))
                if item.get("target_username") is not None
                else None
            ),
            detail=str(item.get("detail")) if item.get("detail") is not None else None,
        )
        for item in auth_store.get("audit_events", [])
        if isinstance(item, dict)
    ]
    return items[-limit:][::-1]


def record_security_audit_event(
    event_type: str,
    *,
    actor_username: str | None = None,
    target_username: str | None = None,
    detail: str | None = None,
) -> None:
    """Persist one explicit audit event."""
    append_security_audit_event(
        event_type,
        actor_username=actor_username,
        target_username=target_username,
        detail=detail,
    )
    persist_raw(auth_store)


__all__ = [
    "WebUISecurityAuditEvent",
    "append_security_audit_event",
    "list_security_audit_events",
    "record_security_audit_event",
]
