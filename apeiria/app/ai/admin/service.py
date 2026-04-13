"""Application-facing admin service for AI domain inspection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.models import AIConversationPromptPreview, AIRecentTarget
from apeiria.app.ai.admin.workbench import (
    extract_tool_result_lines,
    select_latest_user_message,
    to_context_turns,
)
from apeiria.app.ai.conversation.service import ai_conversation_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.memory.service import AIMemoryQuery, ai_memory_service
from apeiria.app.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.app.ai.model.chat_model_service import (
    AIChatModelCreateInput,
    ai_chat_model_service,
)
from apeiria.app.ai.model.profile_service import (
    AIModelProfileCreateInput,
    ai_model_profile_service,
)
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.model.source_service import AISourceCreateInput, ai_source_service
from apeiria.app.ai.model.sources import (
    UnsupportedAISourcePresetError,
    resolve_client_type_for_preset,
)
from apeiria.app.ai.persona.models import AIPersonaBindingTarget, AIPersonaCreateInput
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
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import (
        AIContextTurnView,
        AIConversationAdminView,
        AIConversationIdentity,
        AIConversationTurnDetailView,
    )
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.model import (
        AIChatModelDefinition,
        AIModelBindingSpec,
        AIModelCatalogItem,
        AIModelProfileDefinition,
        AISourceDefinition,
        AISourcePresetDefinition,
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
        latest_bot_turn_at(context_turns) or context_turns[-1].created_at
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


class AIAdminModelNotFoundError(ValueError):
    """Raised when one requested source-backed model cannot be found."""


class AISourceModelFetchConfigError(ValueError):
    """Raised when source model discovery lacks required runtime config."""

    MISSING_PRESET = "请先选择接入方式。"
    MISSING_API_BASE = "请先填写接口地址。"
    MISSING_API_KEY = "未找到可用的 API 密钥。"

    def __init__(self, detail: str = MISSING_API_KEY) -> None:
        super().__init__(detail)


class AISourceModelFetchUpstreamError(RuntimeError):
    """Raised when upstream source discovery fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class AISourceModelTestConfigError(ValueError):
    """Raised when source model test lacks required runtime config."""

    MISSING_MODEL_IDENTIFIER = "请先选择需要测试的模型。"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class AISourceModelTestUpstreamError(RuntimeError):
    """Raised when upstream source model test fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


MODEL_TEST_PROMPT = "Reply with exactly OK."


def _coerce_source_preset_type(
    preset_type: str,
) -> Literal["openai_compatible", "anthropic_compatible"]:
    if preset_type == "openai_compatible":
        return "openai_compatible"
    if preset_type == "anthropic_compatible":
        return "anthropic_compatible"
    raise UnsupportedAISourcePresetError


def _build_persona_create_input(
    *,
    name: str,
    description: str,
    system_prompt: str,
    style_prompt: str,
    enabled: bool,
) -> AIPersonaCreateInput:
    return AIPersonaCreateInput(
        name=name,
        description=description,
        system_prompt=system_prompt,
        style_prompt=style_prompt,
        enabled=enabled,
    )


class AIAdminService:
    """Read and basic override operations for AI admin routes."""

    def list_source_presets(self) -> tuple["AISourcePresetDefinition", ...]:
        return ai_source_service.list_presets()

    async def list_sources(self) -> list["AISourceDefinition"]:
        async with get_session() as session:
            return await ai_source_service.list_sources(session)

    async def create_source(  # noqa: PLR0913
        self,
        *,
        name: str,
        capability_type: str,
        preset_type: str,
        api_base: str | None,
        api_key_env_name: str | None,
        enabled: bool,
        timeout_seconds: int | None,
        custom_headers: dict[str, str],
        extra_config: dict[str, object],
    ) -> "AISourceDefinition":
        async with get_session() as session:
            await ai_source_service.create_source(
                session,
                AISourceCreateInput(
                    name=name,
                    capability_type=capability_type,  # type: ignore[arg-type]
                    client_type=resolve_client_type_for_preset(
                        _coerce_source_preset_type(preset_type)
                    ),
                    preset_type=_coerce_source_preset_type(preset_type),
                    api_base=api_base,
                    api_key_env_name=api_key_env_name,
                    enabled=enabled,
                    timeout_seconds=timeout_seconds,
                    custom_headers=custom_headers,
                    extra_config=extra_config,
                ),
            )
            await session.commit()
            return (await ai_source_service.list_sources(session))[-1]

    async def update_source(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        name: str,
        capability_type: str,
        preset_type: str,
        api_base: str | None,
        api_key_env_name: str | None,
        enabled: bool,
        timeout_seconds: int | None,
        custom_headers: dict[str, str],
        extra_config: dict[str, object],
    ) -> "AISourceDefinition | None":
        async with get_session() as session:
            row = await ai_source_service.update_source(
                session,
                source_id=source_id,
                create_input=AISourceCreateInput(
                    name=name,
                    capability_type=capability_type,  # type: ignore[arg-type]
                    client_type=resolve_client_type_for_preset(
                        _coerce_source_preset_type(preset_type)
                    ),
                    preset_type=_coerce_source_preset_type(preset_type),
                    api_base=api_base,
                    api_key_env_name=api_key_env_name,
                    enabled=enabled,
                    timeout_seconds=timeout_seconds,
                    custom_headers=custom_headers,
                    extra_config=extra_config,
                ),
            )
            if row is None:
                return None
            await session.commit()
            sources = await ai_source_service.list_sources(session)
            return next((item for item in sources if item.source_id == source_id), None)

    async def delete_source(self, *, source_id: str) -> bool:
        async with get_session() as session:
            deleted = await ai_source_service.delete_source(
                session,
                source_id=source_id,
            )
            if deleted:
                await session.commit()
            return deleted

    async def list_model_profiles(self) -> list["AIModelProfileDefinition"]:
        async with get_session() as session:
            return await ai_model_facade.list_profiles(session)

    async def create_model_profile(  # noqa: PLR0913
        self,
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
    ) -> "AIModelProfileDefinition":
        async with get_session() as session:
            create_input = await self._build_profile_create_input(
                session,
                name=name,
                model_id=model_id,
                task_class=task_class,
                priority=priority,
                enabled=enabled,
                fallback_profile_id=fallback_profile_id,
            )
            await ai_model_profile_service.create_profile(session, create_input)
            await session.commit()
            return (await ai_model_profile_service.list_profiles(session))[-1]

    async def update_model_profile(  # noqa: PLR0913
        self,
        *,
        profile_id: str,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
    ) -> "AIModelProfileDefinition | None":
        async with get_session() as session:
            create_input = await self._build_profile_create_input(
                session,
                name=name,
                model_id=model_id,
                task_class=task_class,
                priority=priority,
                enabled=enabled,
                fallback_profile_id=fallback_profile_id,
            )
            row = await ai_model_profile_service.update_profile(
                session,
                profile_id=profile_id,
                create_input=create_input,
            )
            if row is None:
                return None
            await session.commit()
            profiles = await ai_model_profile_service.list_profiles(session)
            return next(
                (item for item in profiles if item.profile_id == profile_id),
                None,
            )

    async def list_model_bindings(self) -> list["AIModelBindingSpec"]:
        async with get_session() as session:
            return await ai_model_facade.list_bindings(session)

    async def list_source_models(
        self,
        *,
        source_id: str,
    ) -> list["AIChatModelDefinition"]:
        async with get_session() as session:
            return await ai_chat_model_service.list_models(
                session,
                source_id=source_id,
            )

    async def fetch_source_models(
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
    ) -> list["AIModelCatalogItem"]:
        async with get_session() as session:
            stored_source = None
            if source_id:
                sources = await ai_source_service.list_sources(session)
                stored_source = next(
                    (item for item in sources if item.source_id == source_id),
                    None,
                )
            source = self._resolve_source_for_model_fetch(
                stored_source=stored_source,
                preset_type=preset_type,
                api_base=api_base,
                api_key_env_name=api_key_env_name,
            )
            resolved_api_key = api_key or ai_source_service.get_source_api_key(source)
            if not resolved_api_key:
                raise AISourceModelFetchConfigError
            try:
                return await ai_model_facade.list_source_models(
                    source=source,
                    api_key=resolved_api_key,
                )
            except Exception as exc:
                raise AISourceModelFetchUpstreamError(str(exc)) from exc

    async def create_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> "AIChatModelDefinition":
        async with get_session() as session:
            await ai_chat_model_service.create_model(
                session,
                AIChatModelCreateInput(
                    source_id=source_id,
                    model_identifier=model_identifier,
                    display_name=display_name,
                    enabled=enabled,
                    is_default=is_default,
                    extra_params=extra_params,
                ),
            )
            await session.commit()
            models = await ai_chat_model_service.list_models(
                session,
                source_id=source_id,
            )
            return models[0]

    async def update_source_model(  # noqa: PLR0913
        self,
        *,
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> "AIChatModelDefinition | None":
        async with get_session() as session:
            row = await ai_chat_model_service.update_model(
                session,
                model_id=model_id,
                create_input=AIChatModelCreateInput(
                    source_id=source_id,
                    model_identifier=model_identifier,
                    display_name=display_name,
                    enabled=enabled,
                    is_default=is_default,
                    extra_params=extra_params,
                ),
            )
            if row is None:
                return None
            await session.commit()
            models = await ai_chat_model_service.list_models(
                session,
                source_id=source_id,
            )
            return next((item for item in models if item.model_id == model_id), None)

    async def delete_source_model(self, *, model_id: str) -> bool:
        async with get_session() as session:
            deleted = await ai_chat_model_service.delete_model(
                session,
                model_id=model_id,
            )
            if deleted:
                await session.commit()
            return deleted

    async def test_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
        model_identifier: str,
    ) -> tuple[str, str, int]:
        resolved_model_identifier = model_identifier.strip()
        if not resolved_model_identifier:
            raise AISourceModelTestConfigError(
                AISourceModelTestConfigError.MISSING_MODEL_IDENTIFIER
            )

        async with get_session() as session:
            stored_source = None
            if source_id:
                sources = await ai_source_service.list_sources(session)
                stored_source = next(
                    (item for item in sources if item.source_id == source_id),
                    None,
                )
            source = self._resolve_source_for_model_fetch(
                stored_source=stored_source,
                preset_type=preset_type,
                api_base=api_base,
                api_key_env_name=api_key_env_name,
            )
            resolved_api_key = api_key or ai_source_service.get_source_api_key(source)
            if not resolved_api_key:
                raise AISourceModelTestConfigError(
                    AISourceModelFetchConfigError.MISSING_API_KEY
                )
            try:
                response = await ai_model_facade.generate_text_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    prompt=MODEL_TEST_PROMPT,
                    max_tokens=32,
                )
            except Exception as exc:
                raise AISourceModelTestUpstreamError(str(exc)) from exc
            return (
                resolved_model_identifier,
                response.content.strip(),
                len(response.tool_calls),
            )

    async def _build_profile_create_input(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        name: str,
        model_id: str,
        task_class: str,
        priority: int,
        enabled: bool,
        fallback_profile_id: str | None,
    ):
        model = await ai_chat_model_service.get_model(session, model_id=model_id)
        if model is None:
            raise AIAdminModelNotFoundError
        return AIModelProfileCreateInput(
            name=name,
            model_id=model_id,
            task_class=task_class,  # type: ignore[arg-type]
            priority=priority,
            enabled=enabled,
            fallback_profile_id=fallback_profile_id,
        )

    @staticmethod
    def _resolve_source_for_model_fetch(
        *,
        stored_source: "AISourceDefinition | None",
        preset_type: str | None,
        api_base: str | None,
        api_key_env_name: str | None,
    ) -> "AISourceDefinition":
        effective_preset_type = preset_type or (
            stored_source.preset_type if stored_source is not None else None
        )
        if not effective_preset_type:
            raise AISourceModelFetchConfigError(
                AISourceModelFetchConfigError.MISSING_PRESET
            )

        coerced_preset_type = _coerce_source_preset_type(effective_preset_type)
        effective_api_base = (
            api_base
            if api_base is not None
            else stored_source.api_base
            if stored_source
            else None
        )
        if not effective_api_base or not effective_api_base.strip():
            raise AISourceModelFetchConfigError(
                AISourceModelFetchConfigError.MISSING_API_BASE
            )

        effective_api_key_env_name = (
            api_key_env_name
            if api_key_env_name is not None
            else stored_source.api_key_env_name
            if stored_source
            else None
        )

        return ai_source_service.build_ephemeral_source(
            name=stored_source.name if stored_source is not None else "preview_source",
            capability_type=(
                stored_source.capability_type
                if stored_source is not None
                else "chat_completion"
            ),
            client_type=resolve_client_type_for_preset(coerced_preset_type),
            preset_type=coerced_preset_type,
            api_base=effective_api_base.strip(),
            api_key_env_name=(
                effective_api_key_env_name.strip()
                if isinstance(effective_api_key_env_name, str)
                and effective_api_key_env_name.strip()
                else None
            ),
            enabled=stored_source.enabled if stored_source is not None else True,
            timeout_seconds=(
                stored_source.timeout_seconds if stored_source is not None else None
            ),
            custom_headers=(
                stored_source.custom_headers if stored_source is not None else None
            ),
            extra_config=(
                stored_source.extra_config if stored_source is not None else None
            ),
        )

    async def list_personas(self) -> list["AIPersonaDefinition"]:
        async with get_session() as session:
            return await ai_persona_service.list_personas(session)

    async def list_persona_bindings(self) -> list["AIPersonaBindingSpec"]:
        async with get_session() as session:
            return await ai_persona_service.list_bindings(session)

    async def create_persona(
        self,
        *,
        name: str,
        description: str,
        system_prompt: str,
        style_prompt: str,
        enabled: bool,
    ) -> "AIPersonaDefinition":
        async with get_session() as session:
            row = await ai_persona_service.create_persona(
                session,
                _build_persona_create_input(
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    style_prompt=style_prompt,
                    enabled=enabled,
                ),
            )
            await session.commit()
            personas = await ai_persona_service.list_personas(session)
            return next(item for item in personas if item.persona_id == row.persona_id)

    async def update_persona(  # noqa: PLR0913
        self,
        *,
        persona_id: str,
        name: str,
        description: str,
        system_prompt: str,
        style_prompt: str,
        enabled: bool,
    ) -> "AIPersonaDefinition | None":
        async with get_session() as session:
            row = await ai_persona_service.update_persona(
                session,
                persona_id=persona_id,
                create_input=_build_persona_create_input(
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    style_prompt=style_prompt,
                    enabled=enabled,
                ),
            )
            if row is None:
                return None
            await session.commit()
            personas = await ai_persona_service.list_personas(session)
            return next(
                (item for item in personas if item.persona_id == persona_id),
                None,
            )

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

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list[AIRecentTarget]:
        conversations = await self.list_recent_conversations(limit=limit)
        targets: list[AIRecentTarget] = []
        seen_users: set[str] = set()

        for item in conversations:
            summary = (item.short_summary or "").strip()
            conversation_title = summary or item.conversation_id[:12]
            conversation_subtitle = (
                f"{item.platform} · {item.scope_type} · {item.scope_id}"
            )
            targets.append(
                AIRecentTarget(
                    target_type="conversation",
                    subject_type="conversation",
                    subject_id=item.conversation_id,
                    title=conversation_title,
                    subtitle=conversation_subtitle,
                    conversation_id=item.conversation_id,
                    platform=item.platform,
                    scope_type=item.scope_type,
                    scope_id=item.scope_id,
                    subject_user_id=item.subject_user_id,
                    last_active_at=item.last_active_at.isoformat(),
                )
            )

            user_id = item.subject_user_id or (
                item.scope_id if item.scope_type == "private" else None
            )
            if user_id is None or user_id in seen_users:
                continue
            seen_users.add(user_id)
            user_subtitle = f"{item.platform} · {item.scope_type}"
            targets.append(
                AIRecentTarget(
                    target_type="user",
                    subject_type="user",
                    subject_id=user_id,
                    title=user_id,
                    subtitle=user_subtitle,
                    conversation_id=item.conversation_id,
                    platform=item.platform,
                    scope_type=item.scope_type,
                    scope_id=item.scope_id,
                    subject_user_id=user_id,
                    last_active_at=item.last_active_at.isoformat(),
                )
            )

        return targets[: limit * 2]

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
                source_id=(selected.source.source_id if selected is not None else None),
                profile_id=(
                    selected.profile.profile_id if selected is not None else None
                ),
                model_name=(
                    selected.resolved_model_name if selected is not None else None
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
                    social_decision.reason_text if social_decision is not None else None
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

    async def list_relationships(
        self,
        *,
        limit: int = 50,
    ) -> list["AIRelationshipState"]:
        async with get_session() as session:
            return await ai_relationship_service.list_states(session, limit=limit)

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
