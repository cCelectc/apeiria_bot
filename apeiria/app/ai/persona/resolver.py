"""Pure persona binding resolution rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaBindingTarget,
    )


def resolve_persona_binding(
    bindings: list[AIPersonaBindingSpec],
    target: AIPersonaBindingTarget,
) -> AIPersonaBindingSpec | None:
    """Resolve the effective persona binding for one AI scene.

    Priority order:

    1. conversation
    2. user
    3. group
    4. global
    """

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
