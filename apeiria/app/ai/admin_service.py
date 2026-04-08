"""Application-facing admin service for AI domain inspection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.memory.service import AIMemoryQuery, ai_memory_service
from apeiria.app.ai.models.client import ai_model_client
from apeiria.app.ai.models.factory import build_provider_adapter
from apeiria.app.ai.models.service import ai_model_service
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.providers.service import ai_provider_service
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.app.ai.tools.resolver import (
    AIToolSceneContext,
    AIToolScenePolicyProfile,
    resolve_default_tool_policy,
)
from apeiria.app.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.models.bindings import AIModelBindingSpec
    from apeiria.app.ai.models.models import AIModelProfileDefinition
    from apeiria.app.ai.models.provider import AIProviderModelItem
    from apeiria.app.ai.persona.models import (
        AIPersonaBindingSpec,
        AIPersonaDefinition,
    )
    from apeiria.app.ai.providers.models import AIProviderDefinition
    from apeiria.app.ai.relationship.models import AIRelationshipState
    from apeiria.app.ai.tools.models import (
        AIToolExecutionView,
        AIToolPolicy,
        AIToolSpec,
    )


class AIAdminService:
    """Read and basic override operations for AI admin routes."""

    async def list_providers(self) -> list[AIProviderDefinition]:
        async with get_session() as session:
            return await ai_provider_service.list_providers(session)

    async def list_model_profiles(self) -> list[AIModelProfileDefinition]:
        async with get_session() as session:
            return await ai_model_service.list_profiles(session)

    async def list_model_bindings(self) -> list[AIModelBindingSpec]:
        async with get_session() as session:
            return await ai_model_service.list_bindings(session)

    async def list_provider_models(
        self,
        *,
        provider_id: str,
        api_key: str,
    ) -> list[AIProviderModelItem]:
        async with get_session() as session:
            providers = await ai_provider_service.list_providers(session)
        provider = next(
            (item for item in providers if item.provider_id == provider_id),
            None,
        )
        if provider is None:
            return []

        ai_model_client.registry.register(
            provider.provider_id,
            build_provider_adapter(
                provider,
                api_key=api_key or ai_provider_service.get_provider_api_key(provider),
            ),
        )
        return await ai_model_client.list_models(
            provider_id=provider.provider_id,
            api_key=api_key,
        )

    async def list_personas(self) -> list[AIPersonaDefinition]:
        async with get_session() as session:
            return await ai_persona_service.list_personas(session)

    async def list_persona_bindings(self) -> list[AIPersonaBindingSpec]:
        async with get_session() as session:
            return await ai_persona_service.list_bindings(session)

    async def list_memories(
        self,
        *,
        subject_type: str,
        subject_id: str,
        query_text: str = "",
        limit: int = 20,
    ) -> list[AIMemoryDefinition]:
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

    async def get_relationship_state(
        self,
        *,
        platform: str,
        user_id: str,
        group_id: str | None = None,
    ) -> AIRelationshipState:
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
    ) -> AIRelationshipState:
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

    def list_tools(self, policy: AIToolPolicy | None = None) -> list[AIToolSpec]:
        if policy is None:
            return ai_tool_service.registry.list_tools()
        return ai_tool_service.list_allowed_tools(policy)

    def preview_tool_policy(
        self,
        *,
        scope_type: str,
        is_tome: bool,
        allow_read_only_tools: bool = True,
        capability_mode: str = "off",
    ) -> AIToolPolicy:
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

    async def list_tool_executions(
        self,
        *,
        conversation_id: str,
    ) -> list[AIToolExecutionView]:
        async with get_session() as session:
            return await ai_tool_service.list_executions(
                session,
                conversation_id=conversation_id,
            )


ai_admin_service = AIAdminService()
