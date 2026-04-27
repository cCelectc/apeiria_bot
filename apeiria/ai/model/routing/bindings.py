"""Pure model profile binding resolution rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIModelBindingSpec:
    """One resolved model profile binding record."""

    binding_id: str
    scope_type: str
    scope_id: str
    profile_id: str


@dataclass(frozen=True)
class AIModelBindingTarget:
    """Binding target derived from the current AI scene."""

    conversation_id: str
    group_id: str | None
    user_id: str | None


def resolve_model_binding(
    bindings: list[AIModelBindingSpec],
    target: AIModelBindingTarget,
) -> AIModelBindingSpec | None:
    """Resolve the effective model profile binding for one AI scene."""

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
