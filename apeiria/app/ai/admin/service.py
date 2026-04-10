"""Application-facing admin service for AI domain inspection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.conversation.service import ai_conversation_service
from apeiria.app.ai.memory.service import AIMemoryQuery, ai_memory_service
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.relationship.service import ai_relationship_service
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
    from apeiria.app.ai.conversation.models import (
        AIConversationAdminView,
        AIConversationTurnDetailView,
    )
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.model import (
        AIModelBindingSpec,
        AIModelProfileDefinition,
        AIProviderDefinition,
        AIProviderModelItem,
    )
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.app.ai.relationship.models import AIRelationshipState
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


class AIAdminService:
    """Read and basic override operations for AI admin routes."""

    async def list_providers(self) -> list["AIProviderDefinition"]:
        async with get_session() as session:
            return await ai_model_facade.list_providers(session)

    async def list_model_profiles(self) -> list["AIModelProfileDefinition"]:
        async with get_session() as session:
            return await ai_model_facade.list_profiles(session)

    async def list_model_bindings(self) -> list["AIModelBindingSpec"]:
        async with get_session() as session:
            return await ai_model_facade.list_bindings(session)

    async def list_provider_models(
        self,
        *,
        provider_id: str,
        api_key: str,
    ) -> list["AIProviderModelItem"]:
        async with get_session() as session:
            return await ai_model_facade.list_provider_models(
                session,
                provider_id=provider_id,
                api_key=api_key,
            )

    async def list_personas(self) -> list["AIPersonaDefinition"]:
        async with get_session() as session:
            return await ai_persona_service.list_personas(session)

    async def list_persona_bindings(self) -> list["AIPersonaBindingSpec"]:
        async with get_session() as session:
            return await ai_persona_service.list_bindings(session)

    async def list_memories(
        self,
        *,
        subject_type: str,
        subject_id: str,
        query_text: str = "",
        limit: int = 20,
    ) -> list["AIMemoryDefinition"]:
        async with get_session() as session:
            if query_text.strip():
                return await ai_memory_service.retrieve_memories(
                    session,
                    AIMemoryQuery(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        query_text=query_text,
                        limit=limit,
                    ),
                )
            memories = await ai_memory_service.list_memories(
                session,
                subject_type=subject_type,
                subject_id=subject_id,
            )
            return memories[:limit]

    async def list_recent_conversations(
        self,
        *,
        limit: int = 20,
    ) -> list["AIConversationAdminView"]:
        async with get_session() as session:
            return await ai_conversation_service.list_recent_conversations(
                session,
                limit=limit,
            )

    async def list_conversation_turns(
        self,
        *,
        conversation_id: str,
        limit: int = 50,
    ) -> list["AIConversationTurnDetailView"]:
        async with get_session() as session:
            return await ai_conversation_service.list_turns_for_conversation(
                session,
                conversation_id=conversation_id,
                limit=limit,
            )

    async def get_relationship_state(
        self,
        *,
        platform: str,
        user_id: str,
        group_id: str | None = None,
    ) -> "AIRelationshipState":
        async with get_session() as session:
            return await ai_relationship_service.get_state(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
            )

    async def set_relationship_score(
        self,
        *,
        platform: str,
        user_id: str,
        score: float,
        group_id: str | None = None,
    ) -> "AIRelationshipState":
        async with get_session() as session:
            state = await ai_relationship_service.set_manual_score(
                session,
                platform=platform,
                group_id=group_id,
                user_id=user_id,
                score=score,
            )
            await session.commit()
            return state

    def list_tools(self, policy: "AIToolPolicy | None" = None) -> list["AIToolSpec"]:
        return ai_tool_service.list_tool_specs(policy)

    def list_capabilities(self) -> list["AICapabilityDefinition"]:
        return ai_tool_service.list_capabilities()

    def list_skills(
        self,
        policy: "AIToolPolicy | None" = None,
    ) -> list["AISkillDefinition"]:
        return ai_skill_service.list_skills(policy)

    def preview_tool_intents(
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
        return ai_tool_service.preview_tool_intents(
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
            return AIToolPolicyBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                allow_read_only_tools=row.allow_read_only_tools,
                capability_mode=row.capability_mode,  # type: ignore[arg-type]
            )

    async def update_tool_policy_binding(
        self,
        *,
        binding_id: str,
        allow_read_only_tools: bool,
        capability_mode: str,
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
            return AIToolPolicyBindingSpec(
                binding_id=row.binding_id,
                scope_type=row.scope_type,
                scope_id=row.scope_id,
                allow_read_only_tools=row.allow_read_only_tools,
                capability_mode=row.capability_mode,  # type: ignore[arg-type]
            )

    async def delete_tool_policy_binding(
        self,
        *,
        binding_id: str,
    ) -> bool:
        async with get_session() as session:
            deleted = await ai_tool_policy_binding_service.delete_binding(
                session,
                binding_id=binding_id,
            )
            if deleted:
                await session.commit()
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
        conversation_id: str,
    ) -> list["AIToolExecutionView"]:
        async with get_session() as session:
            return await ai_tool_service.list_executions(
                session,
                conversation_id=conversation_id,
            )


ai_admin_service = AIAdminService()

__all__ = ["AIAdminService", "ai_admin_service"]
