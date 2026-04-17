"""Application models for access control and runtime decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SubjectType = Literal["user", "group"]
RuleEffect = Literal["allow", "deny"]
ConversationType = Literal["private", "group", "other"]


@dataclass(frozen=True)
class AccessContext:
    """Normalized access context for one incoming event."""

    user_id: str
    group_id: str | None
    conversation_type: ConversationType
    is_superuser: bool
    adapter_role_level: int


@dataclass(frozen=True)
class AccessPolicyRule:
    """One explicit allow/deny rule bound to one subject and plugin."""

    subject_type: SubjectType
    subject_id: str
    plugin_module: str
    effect: RuleEffect
    note: str | None = None


@dataclass(frozen=True)
class PluginPolicy:
    """Framework-owned governance policy for one plugin."""

    plugin_module: str
    access_mode: Literal["default_allow", "default_deny"]
    required_level: int
    protection_mode: Literal["normal", "required"]
    visibility: Literal["normal", "hidden"] = "normal"
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class PermissionDecision:
    """Unified runtime permission decision with governance context."""

    allowed: bool
    code: str
    reason: str | None = None
    source: str = "runtime"
    degradation: dict[str, object] | None = None
    details: dict[str, object] | None = None
