"""Principal role registry and capability helpers."""

from __future__ import annotations

from typing import Final

from apeiria.shared.principal import PrincipalRole

ROLE_OWNER: Final = "owner"
CAP_CONTROL_PANEL: Final = "control_panel"
CAP_ACCOUNT_MANAGE: Final = "account_manage"

ROLE_REGISTRY: Final[dict[str, PrincipalRole]] = {
    ROLE_OWNER: PrincipalRole(
        role_id=ROLE_OWNER,
        capabilities=(CAP_CONTROL_PANEL, CAP_ACCOUNT_MANAGE),
    ),
}
SUPPORTED_ASSIGNABLE_ROLES: Final[frozenset[str]] = frozenset(ROLE_REGISTRY)


def normalize_role(role: object) -> str:
    """Normalize persisted or user-provided role names."""

    if not isinstance(role, str):
        return ""
    return role.strip().lower()


def normalize_supported_role(role: object, *, fallback: str = "") -> str:
    """Normalize one role and reject unsupported values."""

    normalized = normalize_role(role)
    if normalized in ROLE_REGISTRY:
        return normalized
    return fallback


def role_for(role: object, *, fallback: str = "") -> PrincipalRole | None:
    """Resolve one role id into the registered role object."""

    normalized = normalize_supported_role(role, fallback=fallback)
    if not normalized:
        return None
    return ROLE_REGISTRY.get(normalized)


def capabilities_for_role(role: object) -> list[str]:
    """Return capabilities for one role identifier."""

    resolved = role_for(role)
    return list(resolved.capabilities) if resolved is not None else []


def has_capability(role: object, capability: str) -> bool:
    """Return whether one role identifier contains the requested capability."""

    resolved = role_for(role)
    return capability in resolved.capabilities if resolved is not None else False


def can_access_control_panel(role: object) -> bool:
    """Return whether one role may enter the control panel."""

    return has_capability(role, CAP_CONTROL_PANEL)


def can_manage_accounts(role: object) -> bool:
    """Return whether one role may manage Web UI accounts."""

    return has_capability(role, CAP_ACCOUNT_MANAGE)
