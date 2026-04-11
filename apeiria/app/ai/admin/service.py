"""Application-facing admin service for AI domain inspection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.models import AIConversationPromptPreview
from apeiria.app.ai.admin.workbench import (
    extract_tool_result_lines,
    select_latest_user_message,
    to_context_turns,
)
from apeiria.app.ai.conversation.service import ai_conversation_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.memory.service import AIMemoryQuery, ai_memory_service
from apeiria.app.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.app.ai.runtime.composer import AIRuntimeComposeInput, compose_reply_prompt
from apeiria.app.ai.runtime.memory_steps import retrieve_memories_for_preview
from apeiria.app.ai.runtime.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.skills.service import ai_skill_service
from apeiria.app.ai.social_policy import (
    ai_social_policy_service,
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    summarize_social_policy_decision,
)
from apeiria.app.ai.tools.policy import (
    AIToolPolicyBindingCreateInput,
    AIToolPolicyBindingSpec,
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    AIToolScenePolicyProfile,
    ai_tool_policy_binding_service,
    resolve_default_tool_policy,
    summarize_tool_policy,
)
from apeiria.app.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import (
        AIContextTurnView,
        AIConversationAdminView,
        AIConversationIdentity,
        AIConversationTurnDetailView,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
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


def _build_prompt_preview_social_input(  # noqa: PLR0913
    *,
    conversation_id: str,
    identity: "AIConversationIdentity",
    latest_user_message: str,
    conversation_summary: str | None,
    relationship_context: str | None,
    persona_id: str | None,
    allowed_tool_names: tuple[str, ...],
    context_turns: list["AIContextTurnView"],
):
    from apeiria.app.ai.social_policy import AISocialPolicyInput

    decision_time = (
        latest_bot_turn_at(context_turns)
        or context_turns[-1].created_at
        if context_turns
        else datetime.now(timezone.utc)
    )
    return AISocialPolicyInput(
        conversation_id=conversation_id,
        scene_type=identity.scope_type,
        message_text=latest_user_message,
        latest_user_turn_text=latest_user_turn_text(context_turns),
        conversation_summary=conversation_summary,
        relationship_context=relationship_context,
        persona_id=persona_id,
        available_tool_names=allowed_tool_names,
        recent_turn_count=len(context_turns),
        recent_bot_turn_count=count_recent_bot_turns(context_turns),
        last_bot_turn_at=latest_bot_turn_at(context_turns),
        current_time=decision_time,
        runtime_mode="message",
        is_direct_wake=(identity.scope_type == "private"),
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

    async def list_future_tasks(
        self,
        *,
        limit: int = 20,
    ) -> list["AIFutureTaskDefinition"]:
        async with get_session() as session:
            return await ai_future_task_service.list_tasks(session, limit=limit)

    async def cancel_future_task(
        self,
        *,
        task_id: str,
    ) -> "AIFutureTaskDefinition | None":
        async with get_session() as session:
            task = await ai_future_task_service.cancel_task(session, task_id=task_id)
            if task is not None:
                await session.commit()
            return task

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

    async def build_prompt_preview(
        self,
        *,
        conversation_id: str,
        turn_limit: int = 50,
    ) -> AIConversationPromptPreview | None:
        async with get_session() as session:
            conversation = await ai_conversation_service.get_conversation_view(
                session,
                conversation_id=conversation_id,
            )
            if conversation is None:
                return None
            identity = await ai_conversation_service.get_conversation_identity(
                session,
                conversation_id=conversation_id,
            )
            if identity is None:
                return None
            turns = await ai_conversation_service.list_turns_for_conversation(
                session,
                conversation_id=conversation_id,
                limit=turn_limit,
            )
            latest_user_message = select_latest_user_message(turns)
            user_id = identity.subject_user_id or identity.scope_id
            relationship_target = build_relationship_target(identity, user_id)
            relationship_context = await load_relationship_context(
                session,
                target=relationship_target,
            )
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=AIPersonaBindingTarget(
                    conversation_id=identity.conversation_id,
                    group_id=(
                        identity.scope_id if identity.scope_type == "group" else None
                    ),
                    user_id=identity.subject_user_id or user_id,
                ),
            )
            tool_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
                session,
                scene_context=AIToolSceneContext(
                    scope_type=identity.scope_type,
                    is_tome=identity.scope_type == "private",
                ),
                target=AIToolPolicyBindingTarget(
                    conversation_id=identity.conversation_id,
                    group_id=(
                        identity.scope_id if identity.scope_type == "group" else None
                    ),
                    user_id=identity.subject_user_id,
                ),
            )
            memories = (
                await retrieve_memories_for_preview(
                    session,
                    identity=identity,
                    user_id=user_id,
                    query_text=latest_user_message or "",
                )
                if latest_user_message
                else []
            )
            selected = await ai_model_facade.select_model(
                session,
                query=AIModelRouteQuery(task_class="reply_default"),
                target=AIModelBindingTarget(
                    conversation_id=identity.conversation_id,
                    group_id=(
                        identity.scope_id if identity.scope_type == "group" else None
                    ),
                    user_id=identity.subject_user_id or user_id,
                ),
            )
            tool_results = extract_tool_result_lines(turns)
            tool_policy_text = summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                tool_policy,
            )
            allowed_tools = ai_tool_service.list_allowed_tools(tool_policy)
            context_turns = to_context_turns(turns)
            social_decision = (
                await ai_social_policy_service.decide(
                    session,
                    _build_prompt_preview_social_input(
                        conversation_id=conversation_id,
                        identity=identity,
                        latest_user_message=latest_user_message,
                        conversation_summary=conversation.short_summary,
                        relationship_context=relationship_context,
                        persona_id=persona.persona_id if persona is not None else None,
                        allowed_tool_names=tuple(tool.name for tool in allowed_tools),
                        context_turns=context_turns,
                    ),
                    target=AIModelBindingTarget(
                        conversation_id=identity.conversation_id,
                        group_id=(
                            identity.scope_id
                            if identity.scope_type == "group"
                            else None
                        ),
                        user_id=identity.subject_user_id or user_id,
                    ),
                )
                if latest_user_message
                else None
            )
            rendered_prompt = (
                compose_reply_prompt(
                    AIRuntimeComposeInput(
                        persona=persona,
                        relationship=relationship_context,
                        skill_policy=tool_policy_text,
                        skill_results=tool_results,
                        memories=memories,
                        conversation_summary=conversation.short_summary,
                        social_policy_summary=(
                            summarize_social_policy_decision(social_decision)
                            if social_decision is not None
                            else None
                        ),
                        turns=context_turns,
                    )
                )
                if social_decision is None or social_decision.should_speak
                else "Suppressed by social policy before prompt generation."
            )
            return AIConversationPromptPreview(
                conversation_id=conversation_id,
                latest_user_message=latest_user_message,
                provider_id=(
                    selected.provider.provider_id if selected is not None else None
                ),
                profile_id=(
                    selected.profile.profile_id if selected is not None else None
                ),
                model_name=(
                    selected.profile.model_name if selected is not None else None
                ),
                persona_id=persona.persona_id if persona is not None else None,
                conversation_summary=conversation.short_summary,
                relationship_context=relationship_context,
                tool_policy=tool_policy_text,
                social_action=(
                    social_decision.action if social_decision is not None else None
                ),
                social_tool_mode=(
                    social_decision.tool_mode if social_decision is not None else None
                ),
                social_reason_text=(
                    social_decision.reason_text
                    if social_decision is not None
                    else None
                ),
                social_reason_codes=(
                    social_decision.reason_codes if social_decision is not None else ()
                ),
                social_policy_source=(
                    str(social_decision.evidence.get("policy_source"))
                    if social_decision is not None
                    and social_decision.evidence.get("policy_source") is not None
                    else None
                ),
                tool_results=tool_results,
                memories=tuple(memories),
                rendered_prompt=rendered_prompt,
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
