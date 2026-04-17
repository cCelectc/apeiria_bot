"""Access control application services."""

from .models import (
    AccessContext,
    AccessPolicyRule,
    PermissionDecision,
    PluginPolicy,
)
from .permission import (
    check_permission,
    get_user_level,
    is_group_bot_enabled,
    is_plugin_enabled,
    is_plugin_globally_enabled,
)
from .permission import (
    extract_group_id as extract_group_id_from_session,
)
from .permission_service import PermissionService, permission_service
from .rules import admin_check, ensure_group, ensure_private, owner_check
from .runtime import extract_group_id, group_id_from_event
from .service import AccessService, access_service

__all__ = [
    "AccessContext",
    "AccessPolicyRule",
    "AccessService",
    "PermissionDecision",
    "PermissionService",
    "PluginPolicy",
    "access_service",
    "admin_check",
    "check_permission",
    "ensure_group",
    "ensure_private",
    "extract_group_id",
    "extract_group_id_from_session",
    "get_user_level",
    "group_id_from_event",
    "is_group_bot_enabled",
    "is_plugin_enabled",
    "is_plugin_globally_enabled",
    "owner_check",
    "permission_service",
]
