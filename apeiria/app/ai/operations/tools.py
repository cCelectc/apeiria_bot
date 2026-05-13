"""Tools / capabilities / skills / policies / executions admin operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.skills import ai_skill_service
from apeiria.ai.tools import (
    AIToolLevel,
    AIToolPolicyBindingCreateInput,
    AIToolPolicyBindingSpec,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
    ai_tool_service,
    resolve_default_tool_policy,
)
from apeiria.app.ai.diagnostics.audit import record_ai_admin_audit
from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.runtime.planning.tool_intents import preview_runtime_tool_intents

if TYPE_CHECKING:
    from apeiria.ai.skills import AISkillMetadata
    from apeiria.ai.tools import (
        AIToolDefinition,
        AIToolExecutionView,
        AIToolIntentPreview,
        AIToolPolicy,
    )
    from apeiria.app.ai.lifecycle import AICapabilityInventoryRecord


class ToolsAdminMixin:
    """Admin read/mutation for tools, skills, capabilities, policies, and executions."""

    @staticmethod
    def _ensure_ai_support_ready() -> None:
        ensure_ai_runtime_support_initialized(source="admin_fallback")

    def list_tools(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AIToolDefinition"]:
        self._ensure_ai_support_ready()
        return ai_tool_service.list_tool_specs(policy)

    def list_capabilities(self) -> list["AICapabilityInventoryRecord"]:
        snapshot = ensure_ai_runtime_support_initialized(source="admin_fallback")
        return list(snapshot.capabilities)

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillMetadata"]:
        self._ensure_ai_support_ready()
        return ai_skill_service.list_skills(policy)

    async def preview_tool_intents(
        self,
        *,
        message_text: str,
        scope_type: str,
        is_tome: bool,
        allowed_level: AIToolLevel = AIToolLevel.NONE,
    ) -> list["AIToolIntentPreview"]:
        self._ensure_ai_support_ready()
        policy = self.preview_tool_policy(
            scope_type=scope_type,
            is_tome=is_tome,
            allowed_level=allowed_level,
        )
        return await preview_runtime_tool_intents(
            message_text=message_text,
            policy=policy,
        )

    async def list_tool_policy_bindings(self) -> list[AIToolPolicyBindingSpec]:
        return await ai_tool_policy_binding_service.list_bindings()

    async def create_tool_policy_binding(
        self,
        *,
        scope_type: str,
        scope_id: str,
        allowed_level: AIToolLevel,
        actor_username: str | None = None,
    ) -> AIToolPolicyBindingSpec:
        created = await ai_tool_policy_binding_service.create_binding(
            AIToolPolicyBindingCreateInput(
                scope_type=scope_type,
                scope_id=scope_id,
                allowed_level=allowed_level,
            ),
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
        allowed_level: AIToolLevel,
        actor_username: str | None = None,
    ) -> AIToolPolicyBindingSpec | None:
        updated = await ai_tool_policy_binding_service.update_binding(
            binding_id=binding_id,
            allowed_level=allowed_level,
        )
        if updated is None:
            return None
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
        deleted = await ai_tool_policy_binding_service.delete_binding(
            binding_id=binding_id,
        )
        if deleted:
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
        allowed_level: AIToolLevel | str | None = None,
    ) -> "AIToolPolicy":
        return resolve_default_tool_policy(
            AIToolSceneContext(
                scope_type=scope_type,
                is_tome=is_tome,
            ),
            allowed_level=allowed_level,
        )

    async def list_tool_executions(
        self,
        *,
        session_id: str,
    ) -> list["AIToolExecutionView"]:
        return await ai_tool_service.list_executions(session_id=session_id)


__all__ = ["ToolsAdminMixin"]
