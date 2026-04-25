"""Pure helpers for tool policy bindings and scene evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from apeiria.ai.tools.models import (
    AIToolCapabilityMode,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolSpec,
    AIToolTurnCreateInput,
)
from apeiria.db.runtime import database_runtime


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
        if policy.allowed_tool_names is None or tool.name in policy.allowed_tool_names
    ]
    if not policy.execution_enabled:
        if not preauthorized_tools:
            return (
                "No tools are active for this turn. "
                "Reply using only the visible conversation and recalled context."
            )

        tool_list = ", ".join(
            tool.name for tool in preauthorized_tools[:_MAX_SUMMARY_TOOLS]
        )
        if len(preauthorized_tools) > _MAX_SUMMARY_TOOLS:
            tool_list += ", ..."
        return (
            "Tools are unavailable for this turn. "
            f"Pre-authorized tools for other turns: {tool_list}. "
            "Reply without claiming any external actions."
        )

    allowed_tools = [
        tool for tool in tools if evaluate_tool_policy(tool, policy).allowed
    ]
    if not allowed_tools:
        return "No tools are currently allowed for this scene."

    tool_list = ", ".join(tool.name for tool in allowed_tools[:_MAX_SUMMARY_TOOLS])
    if len(allowed_tools) > _MAX_SUMMARY_TOOLS:
        tool_list += ", ..."
    return (
        "Tools are available only when they add clear value. "
        f"Allowed tools for this scene: {tool_list}. "
        "Keep direct reply as the default path when tools are unnecessary."
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
        allowed_tool_names.update(
            {
                "future_task.manage",
                "memory.query",
                "memory.update",
                "relationship.inspect",
            }
        )

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
    ) -> list[AIToolPolicyBindingSpec]:
        return self._list_bindings_sync()

    async def create_binding(
        self,
        create_input: AIToolPolicyBindingCreateInput,
    ) -> AIToolPolicyBindingSpec:
        binding = AIToolPolicyBindingSpec(
            binding_id=f"tool_policy_bind_{uuid4().hex}",
            scope_type=create_input.scope_type,
            scope_id=create_input.scope_id,
            allow_read_only_tools=create_input.allow_read_only_tools,
            capability_mode=create_input.capability_mode,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_tool_policy (
                    binding_id,
                    scope_type,
                    scope_id,
                    allow_read_only_tools,
                    capability_mode,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    binding.binding_id,
                    binding.scope_type,
                    binding.scope_id,
                    1 if binding.allow_read_only_tools else 0,
                    binding.capability_mode,
                    _utcnow_text(),
                ),
            )
        return binding

    async def update_binding(
        self,
        *,
        binding_id: str,
        allow_read_only_tools: bool,
        capability_mode: AIToolCapabilityMode,
    ) -> AIToolPolicyBindingSpec | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT scope_type, scope_id
                FROM ai_tool_policy
                WHERE binding_id = ?
                """,
                (binding_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE ai_tool_policy
                SET
                    allow_read_only_tools = ?,
                    capability_mode = ?,
                    updated_at = ?
                WHERE binding_id = ?
                """,
                (
                    1 if allow_read_only_tools else 0,
                    capability_mode,
                    _utcnow_text(),
                    binding_id,
                ),
            )
        return AIToolPolicyBindingSpec(
            binding_id=binding_id,
            scope_type=str(row[0]),
            scope_id=str(row[1]),
            allow_read_only_tools=allow_read_only_tools,
            capability_mode=capability_mode,
        )

    async def delete_binding(
        self,
        *,
        binding_id: str,
    ) -> bool:
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                """
                DELETE FROM ai_tool_policy
                WHERE binding_id = ?
                """,
                (binding_id,),
            )
        return cursor.rowcount > 0

    async def resolve_scene_policy(
        self,
        *,
        scene_context: AIToolSceneContext,
        target: AIToolPolicyBindingTarget,
    ) -> AIToolPolicy:
        bindings = await self.list_bindings()
        binding = resolve_tool_policy_binding(bindings, target)
        profile = tool_policy_binding_to_profile(binding)
        return resolve_default_tool_policy(
            scene_context,
            profile or AIToolScenePolicyProfile(),
        )

    def _list_bindings_sync(self) -> list[AIToolPolicyBindingSpec]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    binding_id,
                    scope_type,
                    scope_id,
                    allow_read_only_tools,
                    capability_mode
                FROM ai_tool_policy
                ORDER BY rowid ASC
                """
            ).fetchall()
        return [
            AIToolPolicyBindingSpec(
                binding_id=str(row[0]),
                scope_type=str(row[1]),
                scope_id=str(row[2]),
                allow_read_only_tools=bool(row[3]),
                capability_mode=row[4],
            )
            for row in rows
        ]


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


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
