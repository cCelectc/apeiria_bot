"""Access control — permissions, rules, principal, and audit.

Only re-export lightweight types at package import time. Runtime-facing service
singletons should still be imported from their concrete submodules.
"""

from apeiria.access.audit import AuditActor, AuditEvent, AuditEventKind
from apeiria.access.audit_service import audit_service
from apeiria.access.models import (
    AccessContext,
    AccessPolicyRule,
    PermissionDecision,
    PluginPolicy,
)

__all__ = [
    "AccessContext",
    "AccessPolicyRule",
    "AuditActor",
    "AuditEvent",
    "AuditEventKind",
    "PermissionDecision",
    "PluginPolicy",
    "audit_service",
]
