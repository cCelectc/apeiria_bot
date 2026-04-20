"""Access control — permissions, rules, principal, audit, and WebUI auth.

Only re-export lightweight types at package import time. Service singletons
that require an initialized NoneBot runtime (via nonebot_plugin_orm) must be
imported from their concrete submodules — e.g. ``from apeiria.access.permission
import permission_service``.
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
