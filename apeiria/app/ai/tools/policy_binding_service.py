"""Persistence and resolution service for AI tool policy bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.tools.bindings import (
    AIToolPolicyBindingSpec,
    AIToolPolicyBindingTarget,
    resolve_tool_policy_binding,
    tool_policy_binding_to_profile,
)
from apeiria.app.ai.tools.resolver import (
    AIToolSceneContext,
    AIToolScenePolicyProfile,
    resolve_default_tool_policy,
)
from apeiria.infra.db.models import AIToolPolicyBinding

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.tools.models import AIToolCapabilityMode, AIToolPolicy


@dataclass(frozen=True)
class AIToolPolicyBindingCreateInput:
    """Create payload for one persisted tool policy binding."""

    scope_type: str
    scope_id: str
    allow_read_only_tools: bool = True
    capability_mode: "AIToolCapabilityMode" = "off"


class AIToolPolicyBindingService:
    """Persistence and resolution service for tool policy bindings."""

    async def list_bindings(
        self,
        session: AsyncSession,
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
        session: AsyncSession,
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
        session: AsyncSession,
        *,
        binding_id: str,
        allow_read_only_tools: bool,
        capability_mode: "AIToolCapabilityMode",
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
        session: AsyncSession,
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
        session: AsyncSession,
        *,
        scene_context: AIToolSceneContext,
        target: AIToolPolicyBindingTarget,
    ) -> "AIToolPolicy":
        bindings = await self.list_bindings(session)
        binding = resolve_tool_policy_binding(bindings, target)
        profile = tool_policy_binding_to_profile(binding)
        return resolve_default_tool_policy(
            scene_context,
            profile or AIToolScenePolicyProfile(),
        )


ai_tool_policy_binding_service = AIToolPolicyBindingService()
