"""Governance audit event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

AuditEventKind = Literal[
    "auth.login_succeeded",
    "auth.login_failed",
    "auth.password_changed",
    "auth.sessions_revoked",
    "auth.account_created",
    "auth.account_disabled",
    "auth.account_enabled",
    "auth.account_deleted",
    "auth.owner_account_recovered",
    "plugin.toggle",
    "plugin.policy_update",
    "plugin.uninstalled",
    "config.update",
    "permission.denied",
]

AuditOutcome = Literal["succeeded", "failed"]


@dataclass(frozen=True)
class AuditActor:
    """Minimal description of who performed a governance action."""

    actor_kind: str
    actor_id: str
    display_name: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """One governance-meaningful action."""

    kind: AuditEventKind
    occurred_at: datetime
    actor: AuditActor | None = None
    target_kind: str | None = None
    target_id: str | None = None
    outcome: AuditOutcome = "succeeded"
    detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
