"""Pure helpers for level-based tool policy bindings and exposure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolLevel,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolTurnCreateInput,
    coerce_tool_level,
    tool_level_allows,
)
from apeiria.db.runtime import database_runtime


@dataclass(frozen=True)
class AIToolSceneContext:
    """Minimal scene facts required for default tool-policy resolution."""

    scope_type: str
    is_tome: bool


@dataclass(frozen=True)
class AIToolPolicyBindingSpec:
    """One persisted tool policy binding record."""

    binding_id: str
    scope_type: str
    scope_id: str
    allowed_level: AIToolLevel


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
    allowed_level: AIToolLevel = AIToolLevel.NONE


_MAX_SUMMARY_TOOLS = 5


def evaluate_tool_policy(
    tool: AIToolDefinition,
    policy: AIToolPolicy,
) -> AIToolPolicyDecision:
    """Return whether one executable tool is allowed by scene policy."""

    if not tool.enabled:
        return AIToolPolicyDecision(allowed=False, reason="tool is disabled")
    if not tool.readiness.ready:
        return AIToolPolicyDecision(allowed=False, reason=tool.readiness.reason)
    if not tool_level_allows(policy.allowed_level, tool.required_level):
        return AIToolPolicyDecision(
            allowed=False,
            reason=(
                f"requires {tool.required_level.value}, "
                f"scene allows {policy.allowed_level.value}"
            ),
        )
    return AIToolPolicyDecision(allowed=True, reason="allowed")


def summarize_tool_policy(
    tools: list[AIToolDefinition],
    policy: AIToolPolicy,
) -> str:
    """Build a compact textual summary of level-based tool availability."""

    allowed_tools = [
        tool for tool in tools if evaluate_tool_policy(tool, policy).allowed
    ]
    if not allowed_tools:
        return (
            "当前场景没有可用的可执行工具。"
            f"当前场景最多允许 {policy.allowed_level.value} 级工具。"
        )

    tool_list = ", ".join(tool.name for tool in allowed_tools[:_MAX_SUMMARY_TOOLS])
    if len(allowed_tools) > _MAX_SUMMARY_TOOLS:
        tool_list += ", ..."
    return (
        "只有在确实带来明确价值时才使用可执行工具。"
        f"当前场景最多允许 {policy.allowed_level.value} 级工具；"
        f"可用工具包括：{tool_list}。"
        "当不需要外部动作时，优先直接回复。"
    )


def resolve_default_tool_policy(
    context: AIToolSceneContext,
    allowed_level: AIToolLevel | str | None = None,
) -> AIToolPolicy:
    """Return conservative default tool policy for one scene."""

    if allowed_level is not None:
        return AIToolPolicy(allowed_level=coerce_tool_level(allowed_level))
    if context.scope_type == "private" or context.is_tome:
        return AIToolPolicy(allowed_level=AIToolLevel.READ)
    return AIToolPolicy(allowed_level=AIToolLevel.NONE)


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


class AIToolPolicyBindingService:
    """Persistence and resolution service for tool policy bindings."""

    async def list_bindings(self) -> list[AIToolPolicyBindingSpec]:
        return self._list_bindings_sync()

    async def create_binding(
        self,
        create_input: AIToolPolicyBindingCreateInput,
    ) -> AIToolPolicyBindingSpec:
        binding = AIToolPolicyBindingSpec(
            binding_id=f"tool_policy_bind_{uuid4().hex}",
            scope_type=create_input.scope_type,
            scope_id=create_input.scope_id,
            allowed_level=create_input.allowed_level,
        )
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_tool_policy (
                    binding_id,
                    scope_type,
                    scope_id,
                    allowed_level,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    binding.binding_id,
                    binding.scope_type,
                    binding.scope_id,
                    binding.allowed_level.value,
                    _utcnow_text(),
                ),
            )
        return binding

    async def update_binding(
        self,
        *,
        binding_id: str,
        allowed_level: AIToolLevel,
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
                    allowed_level = ?,
                    updated_at = ?
                WHERE binding_id = ?
                """,
                (
                    allowed_level.value,
                    _utcnow_text(),
                    binding_id,
                ),
            )
        return AIToolPolicyBindingSpec(
            binding_id=binding_id,
            scope_type=str(row[0]),
            scope_id=str(row[1]),
            allowed_level=allowed_level,
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
        if binding is not None:
            return AIToolPolicy(allowed_level=binding.allowed_level)
        return resolve_default_tool_policy(scene_context)

    def _list_bindings_sync(self) -> list[AIToolPolicyBindingSpec]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    binding_id,
                    scope_type,
                    scope_id,
                    allowed_level
                FROM ai_tool_policy
                ORDER BY rowid ASC
                """
            ).fetchall()
        return [
            AIToolPolicyBindingSpec(
                binding_id=str(row[0]),
                scope_type=str(row[1]),
                scope_id=str(row[2]),
                allowed_level=coerce_tool_level(str(row[3])),
            )
            for row in rows
        ]


ai_tool_policy_binding_service = AIToolPolicyBindingService()

__all__ = [
    "AIToolLevel",
    "AIToolPolicy",
    "AIToolPolicyBindingCreateInput",
    "AIToolPolicyBindingService",
    "AIToolPolicyBindingSpec",
    "AIToolPolicyBindingTarget",
    "AIToolSceneContext",
    "AIToolTurnCreateInput",
    "ai_tool_policy_binding_service",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
]


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
