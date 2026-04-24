"""Web UI role helpers re-exported for the HTTP interface layer."""

from apeiria.access.principal_roles import (
    CAP_ACCOUNT_MANAGE,
    CAP_CONTROL_PANEL,
    ROLE_OWNER,
    ROLE_REGISTRY,
    SUPPORTED_ASSIGNABLE_ROLES,
    can_access_control_panel,
    can_manage_accounts,
    capabilities_for_role,
    has_capability,
    normalize_role,
    normalize_supported_role,
    role_for,
)

__all__ = [
    "CAP_ACCOUNT_MANAGE",
    "CAP_CONTROL_PANEL",
    "ROLE_OWNER",
    "ROLE_REGISTRY",
    "SUPPORTED_ASSIGNABLE_ROLES",
    "can_access_control_panel",
    "can_manage_accounts",
    "capabilities_for_role",
    "has_capability",
    "normalize_role",
    "normalize_supported_role",
    "role_for",
]
