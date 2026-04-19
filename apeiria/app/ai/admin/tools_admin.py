"""Tools / capabilities / skills / policies / executions admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.skills.service import ai_skill_service
from apeiria.app.ai.tools.policy import (
    AIToolPolicyBindingCreateInput,
    AIToolPolicyBindingSpec,
    AIToolSceneContext,
    AIToolScenePolicyProfile,
    ai_tool_policy_binding_service,
    resolve_default_tool_policy,
)
from apeiria.app.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from apeiria.app.ai.skills.catalog import AISkillDefinition
    from apeiria.app.ai.tools.debug import (
        AICapabilityDefinition,
        AICapabilityPreview,
        AIToolIntentPreview,
    )
    from apeiria.app.ai.tools.models import (
        AIToolExecutionView,
        AIToolPolicy,
        AIToolSpec,
    )


class ToolsAdminMixin:
    """Admin read/mutation for tools, skills, capabilities, policies, and executions."""

    def list_tools(self, policy: "AIToolPolicy | None" = None) -> list["AIToolSpec"]:
        return ai_tool_service.list_tool_specs(policy)

    def list_capabilities(self) -> list["AICapabilityDefinition"]:
        return ai_tool_service.list_capabilities()

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillDefinition"]:
        return ai_skill_service.list_skills(policy)

    async def preview_tool_intents(
        self,
        *,
        message_text: str,
        scope_type: str,
        is_tome: bool,
        allow_read_only_tools: bool = True,
        capability_mode: str = "off",
    ) -> list["AIToolIntentPreview"]:
        policy = self.preview_tool_policy(
            scope_type=scope_type,
            is_tome=is_tome,
            allow_read_only_tools=allow_read_only_tools,
            capability_mode=capability_mode,
        )
        async with get_session() as session:
            return await ai_tool_service.preview_tool_intents(
                session=session,
                message_text=message_text,
                policy=policy,
            )

    async def list_tool_policy_bindings(self) -> list[AIToolPolicyBindingSpec]:
        async with get_session() as session:
            return await ai_tool_policy_binding_service.list_bindings(session)

    async def create_tool_policy_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        allow_read_only_tools: bool,
        capability_mode: str,
        actor_username: str | None = None,
    ) -> AIToolPolicyBindingSpec:
        async with get_session() as session:
            row = await ai_tool_policy_binding_service.create_binding(
                session,
                AIToolPolicyBindingCreateInput(
                    scope_type=scope_type,
                    scope_id=scope_id,
                    allow_read_only_tools=allow_read_only_tools,
                    capability_mode=capability_mode,  # type: ignore[arg-type]
                ),
            )
            await session.commit()
            created = AIToolPolicyBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                allow_read_only_tools=row.allow_read_only_tools,
                capability_mode=row.capability_mode,  # type: ignore[arg-type]
            )
            record_ai_admin_audit(
                "ai_tool_policy_binding_created",
                actor_username=actor_username,
                detail=f"{created.binding_id} {created.scope_type}:{created.scope_id}",
            )
            return created

    async def update_tool_policy_binding(
        self,
        *,
        binding_id: str,
        allow_read_only_tools: bool,
        capability_mode: str,
        actor_username: str | None = None,
    ) -> AIToolPolicyBindingSpec | None:
        async with get_session() as session:
            row = await ai_tool_policy_binding_service.update_binding(
                session,
                binding_id=binding_id,
                allow_read_only_tools=allow_read_only_tools,
                capability_mode=capability_mode,  # type: ignore[arg-type]
            )
            if row is None:
                return None
            await session.commit()
            updated = AIToolPolicyBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                allow_read_only_tools=row.allow_read_only_tools,
                capability_mode=row.capability_mode,  # type: ignore[arg-type]
            )
            record_ai_admin_audit(
                "ai_tool_policy_binding_updated",
                actor_username=actor_username,
                detail=f"{updated.binding_id} {updated.scope_type}:{updated.scope_id}",
            )
            return updated

    async def delete_tool_policy_binding(
        self,
        *,
        binding_id: str,
        actor_username: str | None = None,
    ) -> bool:
        async with get_session() as session:
            deleted = await ai_tool_policy_binding_service.delete_binding(
                session,
                binding_id=binding_id,
            )
            if deleted:
                await session.commit()
                record_ai_admin_audit(
                    "ai_tool_policy_binding_deleted",
                    actor_username=actor_username,
                    detail=binding_id,
                )
            return deleted

    def preview_tool_policy(
        self,
        *,
        scope_type: str,
        is_tome: bool,
        allow_read_only_tools: bool = True,
        capability_mode: str = "off",
    ) -> "AIToolPolicy":
        return resolve_default_tool_policy(
            AIToolSceneContext(
                scope_type=scope_type,
                is_tome=is_tome,
            ),
            AIToolScenePolicyProfile(
                allow_read_only_tools=allow_read_only_tools,
                capability_mode=capability_mode,  # type: ignore[arg-type]
            ),
        )

    def preview_capability(
        self,
        *,
        capability_name: str,
        scope_type: str,
        is_tome: bool,
        allow_read_only_tools: bool = True,
        capability_mode: str = "off",
    ) -> "AICapabilityPreview":
        policy = self.preview_tool_policy(
            scope_type=scope_type,
            is_tome=is_tome,
            allow_read_only_tools=allow_read_only_tools,
            capability_mode=capability_mode,
        )
        return ai_tool_service.preview_capability(
            capability_name=capability_name,
            policy=policy,
        )

    async def list_tool_executions(
        self,
        *,
        session_id: str,
    ) -> list["AIToolExecutionView"]:
        async with get_session() as session:
            return await ai_tool_service.list_executions(
                session,
                session_id=session_id,
            )


__all__ = ["ToolsAdminMixin"]
