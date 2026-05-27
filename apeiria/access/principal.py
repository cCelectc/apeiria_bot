"""Formal governance principal and auth session models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

PrincipalKind = Literal[
    "webui_account",
    "bot_subject",
    "system_actor",
    "host_operator",
]
AuthMethod = Literal[
    "password",
    "session_cookie",
    "session_refresh",
    "host_recovery",
]


@dataclass(frozen=True)
class PrincipalRole:
    """Governance-plane role with a resolved capability set."""

    role_id: str
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Principal:
    """Governance-plane identity principal."""

    principal_kind: PrincipalKind
    principal_id: str
    display_name: str
    role: PrincipalRole
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def capabilities(self) -> list[str]:
        return list(self.role.capabilities)


@dataclass(frozen=True)
class AuthSession:
    """Authenticated governance session bound to one principal."""

    principal: Principal
    auth_method: AuthMethod
    session_version: int
    token_subject: str
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    client_ip: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        return self.principal.principal_id

    @property
    def username(self) -> str:
        return self.principal.display_name

    @property
    def role_id(self) -> str:
        return self.principal.role.role_id

    @property
    def capabilities(self) -> list[str]:
        return self.principal.capabilities

    def has_capability(self, capability: str) -> bool:
        return capability in self.principal.role.capabilities
