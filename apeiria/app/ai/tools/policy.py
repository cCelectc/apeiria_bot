"""Pure helpers for tool policy bindings and scene evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.tools.models import (
    AIToolCapabilityMode,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolSpec,
    AIToolTurnCreateInput,
)
from apeiria.infra.db.models import AIToolPolicyBinding

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIToolSceneContext:
    """Minimal scene facts required for default skill-policy resolution."""

    scope_type: str
    is_tome: bool


@dataclass(frozen=True)
class AIToolScenePolicyProfile:
    """Configurable scene-level defaults for skill access."""

    allow_read_only_tools: bool = True
    capability_mode: AIToolCapabilityMode = "off"


@dataclass(frozen=True)
class AIToolPolicyBindingSpec:
    """One persisted tool policy binding record."""

    binding_id: str
    scope_type: str
    scope_id: str
    allow_read_only_tools: bool
    capability_mode: AIToolCapabilityMode


@dataclass(frozen=True)
class AIToolPolicyBindingTarget:
    """Binding target derived from the current AI scene."""

    conversation_id: str
    group_id: str | None
    user_id: str | None


@dataclass(frozen=True)
class AIToolPolicyBindingCreateInput:
    """Create payload for one persisted tool policy binding."""

    scope_type: str
    scope_id: str
    allow_read_only_tools: bool = True
    capability_mode: AIToolCapabilityMode = "off"


_MAX_SUMMARY_TOOLS = 5


def evaluate_tool_policy(
    tool: AIToolSpec,
    policy: AIToolPolicy,
) -> AIToolPolicyDecision:
    """Return whether one skill is allowed under the given scene policy."""

    if not policy.execution_enabled:
        return AIToolPolicyDecision(
            allowed=False,
            reason="tool execution is disabled for this scene",
        )

    if tool.name in policy.denied_tool_names:
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is explicitly denied",
        )

    if (
        policy.allowed_tool_names is not None
        and tool.name not in policy.allowed_tool_names
    ):
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is not in the allowlist",
        )

    if tool.risk_level == "high" and not policy.allow_high_risk_tools:
        return AIToolPolicyDecision(
            allowed=False,
            reason=f"tool '{tool.name}' is high risk and not enabled",
        )

    if tool.is_capability_bridge and not policy.allow_capability_bridge:
        return AIToolPolicyDecision(
            allowed=False,
            reason="NoneBot capability bridge is not enabled",
        )

    return AIToolPolicyDecision(
        allowed=True,
        reason="allowed",
    )


def summarize_tool_policy(
    tools: list[AIToolSpec],
    policy: AIToolPolicy,
) -> str:
    """Build a compact textual summary of tool availability for prompts."""

    preauthorized_tools = [
        tool
        for tool in tools
        if policy.allowed_tool_names is None
        or tool.name in policy.allowed_tool_names
    ]
    if not policy.execution_enabled:
        if not preauthorized_tools:
            return (
                "No external tool execution is enabled in this reply path. "
                "Do not claim to have performed actions outside the visible "
                "chat context."
            )

        tool_list = ", ".join(
            tool.name for tool in preauthorized_tools[:_MAX_SUMMARY_TOOLS]
        )
        if len(preauthorized_tools) > _MAX_SUMMARY_TOOLS:
            tool_list += ", ..."
        return (
            "Tool execution is currently disabled in this reply path. "
            f"Pre-authorized tools for future execution: {tool_list}. "
            "Do not claim to have used any tools in this response."
        )

    allowed_tools = [
        tool
        for tool in tools
        if evaluate_tool_policy(tool, policy).allowed
    ]
    if not allowed_tools:
        return "No tools are currently allowed for this scene."

    tool_list = ", ".join(tool.name for tool in allowed_tools[:_MAX_SUMMARY_TOOLS])
    if len(allowed_tools) > _MAX_SUMMARY_TOOLS:
        tool_list += ", ..."
    return (
        "Tool use is restricted to explicitly allowed capabilities. "
        f"Allowed tools in this scene: {tool_list}. "
        "Do not claim to have used tools that are not listed here."
    )


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


class AIToolPolicyBindingService:
    """Persistence and resolution service for tool policy bindings."""

    async def list_bindings(
        self,
        session: "AsyncSession",
    ) -> list[AIToolPolicyBindingSpec]:
        result = await session.execute(
            select(AIToolPolicyBinding).order_by(AIToolPolicyBinding.id.asc())
        )
        return [
            AIToolPolicyBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                allow_read_only_tools=row.allow_read_only_tools,
                capability_mode=cast("AIToolCapabilityMode", row.capability_mode),
            )
            for row in result.scalars().all()
        ]

    async def create_binding(
        self,
        session: "AsyncSession",
        create_input: AIToolPolicyBindingCreateInput,
    ) -> AIToolPolicyBinding:
        row = AIToolPolicyBinding(
            binding_id=f"tool_policy_bind_{uuid4().hex}",
            scope_type=create_input.scope_type,
            scope_id=create_input.scope_id,
            allow_read_only_tools=create_input.allow_read_only_tools,
            capability_mode=create_input.capability_mode,
        )
        session.add(row)
        await session.flush()
        return row

    async def update_binding(
        self,
        session: "AsyncSession",
        *,
        binding_id: str,
        allow_read_only_tools: bool,
        capability_mode: AIToolCapabilityMode,
    ) -> AIToolPolicyBinding | None:
        result = await session.execute(
            select(AIToolPolicyBinding).where(
                AIToolPolicyBinding.binding_id == binding_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.allow_read_only_tools = allow_read_only_tools
        row.capability_mode = capability_mode
        await session.flush()
        return row

    async def delete_binding(
        self,
        session: "AsyncSession",
        *,
        binding_id: str,
    ) -> bool:
        result = await session.execute(
            select(AIToolPolicyBinding).where(
                AIToolPolicyBinding.binding_id == binding_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        return True

    async def resolve_scene_policy(
        self,
        session: "AsyncSession",
        *,
        scene_context: AIToolSceneContext,
        target: AIToolPolicyBindingTarget,
    ) -> AIToolPolicy:
        bindings = await self.list_bindings(session)
        binding = resolve_tool_policy_binding(bindings, target)
        profile = tool_policy_binding_to_profile(binding)
        return resolve_default_tool_policy(
            scene_context,
            profile or AIToolScenePolicyProfile(),
        )


ai_tool_policy_binding_service = AIToolPolicyBindingService()

__all__ = [
    "AIToolPolicy",
    "AIToolPolicyBindingCreateInput",
    "AIToolPolicyBindingService",
    "AIToolPolicyBindingSpec",
    "AIToolPolicyBindingTarget",
    "AIToolSceneContext",
    "AIToolScenePolicyProfile",
    "AIToolSpec",
    "AIToolTurnCreateInput",
    "ai_tool_policy_binding_service",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
    "tool_policy_binding_to_profile",
]
