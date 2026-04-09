"""Pure tool policy binding resolution rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.tools.resolver import AIToolScenePolicyProfile

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolCapabilityMode


@dataclass(frozen=True)
class AIToolPolicyBindingSpec:
    """One persisted tool policy binding record."""

    binding_id: str
    scope_type: str
    scope_id: str
    allow_read_only_tools: bool
    capability_mode: "AIToolCapabilityMode"


@dataclass(frozen=True)
class AIToolPolicyBindingTarget:
    """Binding target derived from the current AI scene."""

    conversation_id: str
    group_id: str | None
    user_id: str | None


def resolve_tool_policy_binding(
    bindings: list[AIToolPolicyBindingSpec],
    target: AIToolPolicyBindingTarget,
) -> AIToolPolicyBindingSpec | None:
    """Resolve the effective tool policy binding for one AI scene."""

    ordered_scopes: list[tuple[str, str | None]] = [
        ("conversation", target.conversation_id),
        ("user", target.user_id),
        ("group", target.group_id),
        ("global", "__global__"),
    ]

    for scope_type, scope_id in ordered_scopes:
        if not scope_id:
            continue
        for binding in bindings:
            if binding.scope_type == scope_type and binding.scope_id == scope_id:
                return binding
    return None


def tool_policy_binding_to_profile(
    binding: AIToolPolicyBindingSpec | None,
) -> AIToolScenePolicyProfile | None:
    """Convert a binding record into a scene policy profile."""

    if binding is None:
        return None
    return AIToolScenePolicyProfile(
        allow_read_only_tools=binding.allow_read_only_tools,
        capability_mode=binding.capability_mode,
    )
