"""Scene-aware default tool policy resolution."""

from __future__ import annotations

from dataclasses import dataclass

from apeiria.app.ai.tools.models import AIToolPolicy


@dataclass(frozen=True)
class AIToolSceneContext:
    """Minimal scene facts required for default tool-policy resolution."""

    scope_type: str
    is_tome: bool


def resolve_default_tool_policy(context: AIToolSceneContext) -> AIToolPolicy:
    """Return the conservative default tool policy for one scene."""

    allowed_tool_names: set[str] = set()
    if context.scope_type == "private" or context.is_tome:
        allowed_tool_names.update({"memory.query", "relationship.inspect"})

    return AIToolPolicy(
        execution_enabled=bool(allowed_tool_names),
        allowed_tool_names=allowed_tool_names or None,
        allow_high_risk_tools=False,
        allow_capability_bridge=False,
    )
