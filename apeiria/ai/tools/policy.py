"""Pure helpers for level-based tool policy bindings and exposure."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import delete, select, update

from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolLevel,
    AIToolPolicy,
    AIToolPolicyDecision,
    AIToolTurnCreateInput,
    coerce_tool_level,
    tool_level_allows,
)
from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session, rowcount
from apeiria.db.models.ai_tools import AIToolPolicy as AIToolPolicyModel


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
        async with get_session() as session:
            result = await session.execute(
                select(AIToolPolicyModel).order_by(AIToolPolicyModel.binding_id)
            )
            rows = result.scalars().all()
        return [
            AIToolPolicyBindingSpec(
                binding_id=r.binding_id,
                scope_type=r.scope_type,
                scope_id=r.scope_id,
                allowed_level=coerce_tool_level(r.allowed_level),
            )
            for r in rows
        ]

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
        async with get_session() as session:
            session.add(
                AIToolPolicyModel(
                    binding_id=binding.binding_id,
                    scope_type=binding.scope_type,
                    scope_id=binding.scope_id,
                    allowed_level=binding.allowed_level.value,
                    updated_at=_epoch_ms(),
                )
            )
            await session.commit()
        return binding

    async def update_binding(
        self,
        *,
        binding_id: str,
        allowed_level: AIToolLevel,
    ) -> AIToolPolicyBindingSpec | None:
        async with get_session() as session:
            result = await session.execute(
                select(AIToolPolicyModel.scope_type, AIToolPolicyModel.scope_id).where(
                    AIToolPolicyModel.binding_id == binding_id
                )
            )
            row = result.first()
            if row is None:
                return None
            await session.execute(
                update(AIToolPolicyModel)
                .where(AIToolPolicyModel.binding_id == binding_id)
                .values(allowed_level=allowed_level.value, updated_at=_epoch_ms())
            )
            await session.commit()
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
        async with get_session() as session:
            result = await session.execute(
                delete(AIToolPolicyModel).where(
                    AIToolPolicyModel.binding_id == binding_id
                )
            )
            await session.commit()
        return rowcount(result) > 0

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


__all__ = [
    "AIToolLevel",
    "AIToolPolicy",
    "AIToolPolicyBindingCreateInput",
    "AIToolPolicyBindingService",
    "AIToolPolicyBindingSpec",
    "AIToolPolicyBindingTarget",
    "AIToolSceneContext",
    "AIToolTurnCreateInput",
    "evaluate_tool_policy",
    "resolve_default_tool_policy",
    "resolve_tool_policy_binding",
    "summarize_tool_policy",
]
