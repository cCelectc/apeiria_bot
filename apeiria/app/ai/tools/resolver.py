"""Scene-aware default tool policy resolution."""

from __future__ import annotations

from dataclasses import dataclass

from apeiria.app.ai.tools.models import AIToolCapabilityMode, AIToolPolicy


@dataclass(frozen=True)
class AIToolSceneContext:
    """Minimal scene facts required for default tool-policy resolution."""

    scope_type: str
    is_tome: bool


@dataclass(frozen=True)
class AIToolScenePolicyProfile:
    """Configurable scene-level defaults for tool access."""

    allow_read_only_tools: bool = True
    capability_mode: AIToolCapabilityMode = "off"


def resolve_default_tool_policy(
    context: AIToolSceneContext,
    profile: AIToolScenePolicyProfile | None = None,
) -> AIToolPolicy:
    """Return the conservative default tool policy for one scene."""

    profile = profile or AIToolScenePolicyProfile()
    allowed_tool_names: set[str] = set()
    if profile.allow_read_only_tools and (
        context.scope_type == "private" or context.is_tome
    ):
        allowed_tool_names.update({"memory.query", "relationship.inspect"})

    allow_capability_bridge = _allow_capability_bridge(context, profile)
    if allow_capability_bridge:
        allowed_tool_names.add("plugin.capability")

    return AIToolPolicy(
        execution_enabled=bool(allowed_tool_names),
        allowed_tool_names=allowed_tool_names or None,
        allow_high_risk_tools=allow_capability_bridge,
        allow_capability_bridge=allow_capability_bridge,
    )


def _allow_capability_bridge(
    context: AIToolSceneContext,
    profile: AIToolScenePolicyProfile,
) -> bool:
    if profile.capability_mode == "off":
        return False
    if profile.capability_mode == "private_only":
        return context.scope_type == "private"
    return context.scope_type == "private" or context.is_tome
