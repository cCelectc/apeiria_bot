"""Application-facing admin service for AI domain inspection."""

from __future__ import annotations

import io
import re
import wave
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, cast

from nonebot_plugin_orm import get_session

from apeiria.app.ai.admin.audit import record_ai_admin_audit
from apeiria.app.ai.admin.errors import (
    AIAdminModelNotFoundError,
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.app.ai.admin.future_tasks_admin import FutureTasksAdminMixin
from apeiria.app.ai.admin.memories_admin import MemoriesAdminMixin
from apeiria.app.ai.admin.models import (
    AIRecentTarget,
    AISessionPromptChannels,
    AISessionPromptPreview,
)
from apeiria.app.ai.admin.person_profiles_admin import PersonProfilesAdminMixin
from apeiria.app.ai.admin.personas_admin import PersonasAdminMixin
from apeiria.app.ai.admin.relationships_admin import RelationshipsAdminMixin
from apeiria.app.ai.admin.tools_admin import ToolsAdminMixin
from apeiria.app.ai.admin.workbench import (
    extract_tool_result_lines,
    select_latest_user_turn,
    to_context_turns,
)
from apeiria.app.ai.conversation.identity import build_participant_subject_id
from apeiria.app.ai.conversation.service import chat_session_service
from apeiria.app.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.app.ai.model.capability_registry import (
    SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER,
    SOURCE_MODEL_CAPABILITY_REGISTRY,
)
from apeiria.app.ai.model.chat_model_service import (
    ai_chat_model_service,
)
from apeiria.app.ai.model.embedding_model_service import ai_embedding_model_service
from apeiria.app.ai.model.profile_service import (
    AIModelProfileCreateInput,
    ai_model_profile_service,
)
from apeiria.app.ai.model.rerank_model_service import ai_rerank_model_service
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.model.source_service import AISourceCreateInput, ai_source_service
from apeiria.app.ai.model.sources import (
    AISourceCapabilityType,
    AISourcePresetType,
    UnsupportedAISourcePresetError,
    resolve_client_type_for_preset,
)
from apeiria.app.ai.model.stt_model_service import ai_stt_model_service
from apeiria.app.ai.model.tts_model_service import ai_tts_model_service
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import (
    ai_persona_service,
    build_persona_render_context,
)
from apeiria.app.ai.reply_strategy import (
    count_recent_bot_turns,
    latest_bot_turn_at,
    latest_user_turn_text,
    summarize_reply_strategy_decision,
)
from apeiria.app.ai.runtime.composer import (
    AIRuntimeComposeInput,
    build_runtime_prompt_channels,
    compose_pre_tool_reply_prompt,
    compose_roleplay_reply_prompt,
)
from apeiria.app.ai.runtime.memory_steps import (
    load_person_profile_for_prompt,
    retrieve_memories_for_preview,
)
from apeiria.app.ai.runtime.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.runtime.routing import (
    select_post_tool_reply_task_class,
    select_pre_tool_reply_task_class,
)
from apeiria.app.ai.tools.policy import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
    summarize_tool_policy,
)
from apeiria.app.ai.tools.service import ai_tool_service
from apeiria.app.groups import group_service

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import (
        ChatContextMessageView,
        ChatMessageDetailView,
        ChatSessionAdminView,
        ChatSessionIdentity,
    )
    from apeiria.app.ai.model import (
        AIModelBindingSpec,
        AIModelCatalogItem,
        AIModelProfileDefinition,
        AISourceDefinition,
        AISourceModelDefinition,
        AISourcePresetDefinition,
    )
    from apeiria.app.ai.model.capability_registry import (
        AICapabilityModelRegistryEntry,
    )
    from apeiria.app.ai.reply_strategy.models import (
        ReplyStrategyDecision,
        SocialJudgmentInput,
    )
    from apeiria.app.ai.runtime.prompting import AIReplyPromptChannels


def _build_prompt_preview_social_input(  # noqa: PLR0913
    *,
    session_id: str,
    identity: "ChatSessionIdentity",
    latest_user_message: str,
    conversation_summary: str | None,
    relationship_context: str | None,
    persona_id: str | None,
    allowed_tool_names: tuple[str, ...],
    context_turns: list["ChatContextMessageView"],
):
    from apeiria.app.ai.reply_strategy.models import SocialJudgmentInput

    decision_time = (
        latest_bot_turn_at(context_turns) or context_turns[-1].created_at
        if context_turns
        else datetime.now(timezone.utc)
    )
    return SocialJudgmentInput(
        session_id=session_id,
        scene_type=identity.scene_type,
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
        engagement_type="direct",
        initiative_budget_score=None,
        consecutive_silence_count=0,
    )


async def _evaluate_preview_social_judgment(
    session: "AsyncSession",
    *,
    judgment_input: "SocialJudgmentInput",
    target: "AIModelBindingTarget",
) -> "ReplyStrategyDecision":
    """Run social judgment for workbench preview and wrap as ReplyStrategyDecision."""

    from apeiria.app.ai.reply_strategy.models import judgment_to_decision
    from apeiria.app.ai.reply_strategy.social_judgment import (
        evaluate_social_judgment,
    )

    result = await evaluate_social_judgment(
        session,
        judgment_input=judgment_input,
        target=target,
    )
    return judgment_to_decision(result)


def _find_recent_user_name(
    turns: Sequence["ChatContextMessageView | ChatMessageDetailView"],
    user_id: str,
) -> str | None:
    for turn in reversed(turns):
        if turn.author_role != "user" or turn.author_id != user_id:
            continue
        author_name = (turn.author_name or "").strip()
        if author_name:
            return author_name
    return None


async def _load_group_name(identity: "ChatSessionIdentity") -> str | None:
    if identity.scene_type != "group":
        return None
    group = await group_service.get_group(identity.scene_id)
    return group.group_name if group is not None else None


def _to_prompt_channel_preview(
    channels: AIReplyPromptChannels,
) -> AISessionPromptChannels:
    return AISessionPromptChannels(
        mode=channels.mode,
        system_instructions=channels.system.instructions,
        persona=channels.system.persona,
        style=channels.system.style,
        relationship=channels.system.relationship,
        social_policy=channels.system.social_policy,
        tool_policy=channels.system.tool_policy,
        future_task=channels.system.future_task,
        person_profile=channels.person_profile,
        tool_results=channels.tool_results,
        operator_memories=channels.memories.operator,
        summary_memories=channels.memories.summary,
        long_term_memories=channels.memories.long_term,
        knowledge_memories=channels.memories.knowledge,
        conversation_summary=channels.conversation.summary,
        context_priority=channels.conversation.context_priority,
        conversation_messages=channels.conversation.messages,
        response_rules=channels.response_rules,
        instruction=channels.instruction,
    )


MODEL_TEST_PROMPT = "Reply with exactly OK."
EMBEDDING_TEST_TEXT = "Apeiria embedding connectivity check"
TTS_TEST_TEXT = "Apeiria text to speech connectivity check"
RERANK_TEST_QUERY = "Which sentence is about connectivity?"
RERANK_TEST_DOCUMENTS = (
    "This document is unrelated to the task.",
    "This sentence is about connectivity verification.",
    "Another unrelated document.",
)

_REDACTED_TOKEN_TEXT = "[redacted]"
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]+)")
_AUTH_HEADER_PATTERN = re.compile(
    r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?bearer\s+)([A-Za-z0-9._~+/=-]+)"
)


def _sanitize_upstream_error_detail(
    detail: object,
    *,
    secrets: tuple[str | None, ...] = (),
) -> str:
    """Remove obvious credential material from upstream error text."""

    text = str(detail).strip()
    if not text:
        return "upstream request failed"

    sanitized = _BEARER_TOKEN_PATTERN.sub(
        rf"\1{_REDACTED_TOKEN_TEXT}",
        text,
    )
    sanitized = _AUTH_HEADER_PATTERN.sub(
        rf"\1{_REDACTED_TOKEN_TEXT}",
        sanitized,
    )

    for secret in secrets:
        if not isinstance(secret, str):
            continue
        normalized = secret.strip()
        if not normalized:
            continue
        sanitized = sanitized.replace(normalized, _REDACTED_TOKEN_TEXT)

    return sanitized or "upstream request failed"


def _coerce_source_preset_type(
    preset_type: str,
) -> "AISourcePresetType":
    known_preset_types = {item.preset_type for item in ai_source_service.list_presets()}
    if preset_type in known_preset_types:
        return cast("AISourcePresetType", preset_type)
    raise UnsupportedAISourcePresetError


def _build_test_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16000)
    return buffer.getvalue()


def _coerce_optional_string(
    extra_config: dict[str, object] | None,
    key: str,
) -> str | None:
    if not extra_config:
        return None
    value = extra_config.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _coerce_optional_int(
    extra_config: dict[str, object] | None,
    key: str,
) -> int | None:
    if not extra_config:
        return None
    value = extra_config.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _coerce_response_format(
    extra_config: dict[str, object] | None,
    key: str,
) -> Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]:
    value = _coerce_optional_string(extra_config, key)
    if value in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
        return cast("Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']", value)
    return "wav"



class AIAdminService(
    FutureTasksAdminMixin,
    MemoriesAdminMixin,
    PersonasAdminMixin,
    PersonProfilesAdminMixin,
    RelationshipsAdminMixin,
    ToolsAdminMixin,
):
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
        actor_username: str | None = None,
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
            created = (await ai_source_service.list_sources(session))[-1]
            record_ai_admin_audit(
                "ai_source_created",
                actor_username=actor_username,
                detail=f"{created.source_id} {created.name}",
            )
            return created

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
        actor_username: str | None = None,
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
            updated = next(
                (item for item in sources if item.source_id == source_id),
                None,
            )
            if updated is not None:
                record_ai_admin_audit(
                    "ai_source_updated",
                    actor_username=actor_username,
                    detail=f"{updated.source_id} {updated.name}",
                )
            return updated

    async def delete_source(
        self,
        *,
        source_id: str,
        actor_username: str | None = None,
    ) -> bool:
        async with get_session() as session:
            source = await ai_source_service.get_source(session, source_id=source_id)
            dependency_report = await ai_source_service.build_delete_dependency_report(
                session,
                source_id=source_id,
            )
            if dependency_report is not None:
                raise AISourceDeleteBlockedError(
                    model_count=dependency_report.model_count,
                    model_labels=dependency_report.model_labels,
                )
            deleted = await ai_source_service.delete_source(
                session,
                source_id=source_id,
            )
            if deleted:
                await session.commit()
                record_ai_admin_audit(
                    "ai_source_deleted",
                    actor_username=actor_username,
                    detail=(
                        f"{source.source_id} {source.name}"
                        if source is not None
                        else source_id
                    ),
                )
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
        actor_username: str | None = None,
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
            created = (await ai_model_profile_service.list_profiles(session))[-1]
            record_ai_admin_audit(
                "ai_model_profile_created",
                actor_username=actor_username,
                detail=f"{created.profile_id} {created.name}",
            )
            return created

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
        actor_username: str | None = None,
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
            updated = next(
                (item for item in profiles if item.profile_id == profile_id),
                None,
            )
            if updated is not None:
                record_ai_admin_audit(
                    "ai_model_profile_updated",
                    actor_username=actor_username,
                    detail=f"{updated.profile_id} {updated.name}",
                )
            return updated

    async def list_model_bindings(self) -> list["AIModelBindingSpec"]:
        async with get_session() as session:
            return await ai_model_facade.list_bindings(session)

    async def list_source_models(
        self,
        *,
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        async with get_session() as session:
            source = await ai_source_service.get_source(session, source_id=source_id)
            if source is None:
                return []
            return await self._list_managed_models(
                session,
                source=source,
                source_id=source_id,
            )

    async def fetch_source_models(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
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
                extra_config=extra_config,
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
                raise AISourceModelFetchUpstreamError(
                    _sanitize_upstream_error_detail(
                        exc,
                        secrets=(api_key, resolved_api_key),
                    )
                ) from exc

    async def create_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition":
        async with get_session() as session:
            source = await ai_source_service.get_source(session, source_id=source_id)
            if source is None:
                raise AIAdminModelNotFoundError
            await self._create_managed_model(
                session,
                source=source,
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
            )
            await session.commit()
            models = await self.list_source_models(source_id=source_id)
            created = models[0]
            record_ai_admin_audit(
                "ai_source_model_created",
                actor_username=actor_username,
                detail=f"{created.model_id} {created.display_name}",
            )
            return created

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
        actor_username: str | None = None,
    ) -> "AISourceModelDefinition | None":
        async with get_session() as session:
            source = await ai_source_service.get_source(session, source_id=source_id)
            if source is None:
                return None
            row = await self._update_managed_model(
                session,
                source=source,
                model_id=model_id,
                source_id=source_id,
                model_identifier=model_identifier,
                display_name=display_name,
                enabled=enabled,
                is_default=is_default,
                extra_params=extra_params,
            )
            if row is None:
                return None
            await session.commit()
            models = await self.list_source_models(source_id=source_id)
            updated = next((item for item in models if item.model_id == model_id), None)
            if updated is not None:
                record_ai_admin_audit(
                    "ai_source_model_updated",
                    actor_username=actor_username,
                    detail=f"{updated.model_id} {updated.display_name}",
                )
            return updated

    async def delete_source_model(
        self,
        *,
        model_id: str,
        source_id: str | None = None,
        actor_username: str | None = None,
    ) -> bool:
        async with get_session() as session:
            capability_type = await self._resolve_model_capability_type(
                session,
                model_id=model_id,
                source_id=source_id,
            )
            existing_label = await self._build_source_model_audit_label(
                session,
                capability_type=capability_type,
                model_id=model_id,
            )
            dependent_profiles = await self._list_dependent_chat_model_profiles(
                session,
                capability_type=capability_type,
                model_id=model_id,
            )
            if dependent_profiles:
                labels = tuple(profile.name for profile in dependent_profiles[:3])
                raise AISourceModelDeleteBlockedError(
                    profile_count=len(dependent_profiles),
                    profile_labels=labels,
                )
            deleted = False
            if source_id:
                source = await ai_source_service.get_source(
                    session, source_id=source_id
                )
                if source is not None:
                    deleted = await self._delete_managed_model(
                        session,
                        capability_type=source.capability_type,
                        model_id=model_id,
                    )
                else:
                    deleted = await self._delete_managed_model(
                        session,
                        capability_type="chat_completion",
                        model_id=model_id,
                    )
            if not deleted:
                for capability_type in SOURCE_MODEL_CAPABILITY_FALLBACK_ORDER:
                    deleted = await self._delete_managed_model(
                        session,
                        capability_type=capability_type,
                        model_id=model_id,
                    )
                    if deleted:
                        break
            if deleted:
                await session.commit()
                record_ai_admin_audit(
                    "ai_source_model_deleted",
                    actor_username=actor_username,
                    detail=existing_label,
                )
            return deleted

    async def _build_source_model_audit_label(
        self,
        session: "AsyncSession",
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> str:
        if capability_type != "chat_completion":
            return model_id
        existing = await ai_chat_model_service.get_model(session, model_id=model_id)
        if existing is None:
            return model_id
        return f"{existing.model_id} {existing.display_name}"

    async def _list_dependent_chat_model_profiles(
        self,
        session: "AsyncSession",
        *,
        capability_type: "AISourceCapabilityType | None",
        model_id: str,
    ) -> list["AIModelProfileDefinition"]:
        if capability_type != "chat_completion":
            return []
        profiles = await ai_model_profile_service.list_profiles(session)
        return [profile for profile in profiles if profile.model_id == model_id]

    async def test_source_model(  # noqa: PLR0913
        self,
        *,
        source_id: str | None = None,
        preset_type: str | None = None,
        api_base: str | None = None,
        api_key_env_name: str | None = None,
        api_key: str | None = None,
        extra_config: dict[str, object] | None = None,
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
                extra_config=extra_config,
            )
            resolved_api_key = api_key or ai_source_service.get_source_api_key(source)
            if not resolved_api_key:
                raise AISourceModelTestConfigError(
                    AISourceModelFetchConfigError.MISSING_API_KEY
                )
            try:
                if source.capability_type == "embedding":
                    embedding_response = await ai_model_facade.embed_texts_for_source(
                        source=source,
                        api_key=resolved_api_key,
                        model_name=resolved_model_identifier,
                        texts=(EMBEDDING_TEST_TEXT,),
                    )
                    dimensions = (
                        len(embedding_response.vectors[0])
                        if embedding_response.vectors
                        else 0
                    )
                    embedding_summary = (
                        f"{len(embedding_response.vectors)} vector, {dimensions} dims"
                    )
                    return (
                        resolved_model_identifier,
                        f"embedding ok ({embedding_summary})",
                        0,
                    )
                if source.capability_type == "speech_to_text":
                    stt_language = _coerce_optional_string(
                        source.extra_config,
                        "stt_language",
                    )
                    transcription_response = (
                        await ai_model_facade.transcribe_audio_for_source(
                            source=source,
                            api_key=resolved_api_key,
                            model_name=resolved_model_identifier,
                            audio_bytes=_build_test_wav_bytes(),
                            language=stt_language,
                        )
                    )
                    transcription_summary = transcription_response.text.strip()
                    return (
                        resolved_model_identifier,
                        (
                            f"stt ok: {transcription_summary}"
                            if transcription_summary
                            else "stt ok (empty transcript)"
                        ),
                        0,
                    )
                if source.capability_type == "text_to_speech":
                    tts_voice = (
                        _coerce_optional_string(source.extra_config, "tts_voice")
                        or "alloy"
                    )
                    tts_response_format = _coerce_response_format(
                        source.extra_config,
                        "tts_response_format",
                    )
                    speech_response = (
                        await ai_model_facade.synthesize_speech_for_source(
                            source=source,
                            api_key=resolved_api_key,
                            model_name=resolved_model_identifier,
                            text=TTS_TEST_TEXT,
                            voice=tts_voice,
                            response_format=tts_response_format,
                        )
                    )
                    return (
                        resolved_model_identifier,
                        f"tts ok ({len(speech_response.audio_bytes)} bytes)",
                        0,
                    )
                if source.capability_type == "rerank":
                    rerank_top_n = (
                        _coerce_optional_int(source.extra_config, "rerank_top_n") or 2
                    )
                    rerank_response = await ai_model_facade.rerank_documents_for_source(
                        source=source,
                        api_key=resolved_api_key,
                        model_name=resolved_model_identifier,
                        query=RERANK_TEST_QUERY,
                        documents=RERANK_TEST_DOCUMENTS,
                        top_n=rerank_top_n,
                    )
                    top_score = (
                        rerank_response.results[0].relevance_score
                        if rerank_response.results
                        else 0.0
                    )
                    rerank_summary = (
                        f"{len(rerank_response.results)} results, top={top_score:.3f}"
                    )
                    return (
                        resolved_model_identifier,
                        f"rerank ok ({rerank_summary})",
                        0,
                    )
                response = await ai_model_facade.generate_text_for_source(
                    source=source,
                    api_key=resolved_api_key,
                    model_name=resolved_model_identifier,
                    prompt=MODEL_TEST_PROMPT,
                    max_tokens=32,
                )
            except Exception as exc:
                raise AISourceModelTestUpstreamError(
                    _sanitize_upstream_error_detail(
                        exc,
                        secrets=(api_key, resolved_api_key),
                    )
                ) from exc
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
        extra_config: dict[str, object] | None = None,
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
            capability_type=(  # type: ignore[arg-type]
                stored_source.capability_type
                if stored_source is not None
                else next(
                    (
                        item.capability_type
                        for item in ai_source_service.list_presets()
                        if item.preset_type == coerced_preset_type
                    ),
                    "chat_completion",
                )
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
                extra_config
                if extra_config is not None
                else stored_source.extra_config
                if stored_source is not None
                else None
            ),
        )

    async def _create_managed_model(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        source: "AISourceDefinition",
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> None:
        entry = self._get_model_capability_entry(source.capability_type)
        await entry.create_model(
            session,
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
        )

    async def _update_managed_model(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        *,
        source: "AISourceDefinition",
        model_id: str,
        source_id: str,
        model_identifier: str,
        display_name: str,
        enabled: bool,
        is_default: bool,
        extra_params: dict[str, object],
    ) -> object | None:
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.update_model(
            session,
            model_id,
            source_id,
            model_identifier,
            display_name,
            enabled,
            is_default,
            extra_params,
        )

    async def _list_managed_models(
        self,
        session: "AsyncSession",
        *,
        source: "AISourceDefinition",
        source_id: str,
    ) -> list["AISourceModelDefinition"]:
        entry = self._get_model_capability_entry(source.capability_type)
        return await entry.list_models(
            session,
            source_id,
        )

    async def _delete_managed_model(
        self,
        session: "AsyncSession",
        *,
        capability_type: "AISourceCapabilityType",
        model_id: str,
    ) -> bool:
        entry = self._get_model_capability_entry(capability_type)
        return await entry.delete_model(session, model_id)

    async def _resolve_model_capability_type(
        self,
        session: "AsyncSession",
        *,
        model_id: str,
        source_id: str | None = None,
    ) -> "AISourceCapabilityType | None":
        if source_id:
            source = await ai_source_service.get_source(session, source_id=source_id)
            if source is not None:
                return source.capability_type

        lookups = (
            (
                cast("AISourceCapabilityType", "chat_completion"),
                ai_chat_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "embedding"),
                ai_embedding_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "speech_to_text"),
                ai_stt_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "text_to_speech"),
                ai_tts_model_service.get_model,
            ),
            (
                cast("AISourceCapabilityType", "rerank"),
                ai_rerank_model_service.get_model,
            ),
        )
        for capability_type, get_model in lookups:
            if await get_model(session, model_id=model_id) is not None:
                return cast("AISourceCapabilityType", capability_type)
        return None

    @staticmethod
    def _get_model_capability_entry(
        capability_type: "AISourceCapabilityType",
    ) -> "AICapabilityModelRegistryEntry":
        return SOURCE_MODEL_CAPABILITY_REGISTRY[capability_type]

    async def list_recent_sessions(
        self,
        *,
        limit: int = 20,
    ) -> list["ChatSessionAdminView"]:
        async with get_session() as session:
            return await chat_session_service.list_recent_sessions(
                session,
                limit=limit,
            )

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list[AIRecentTarget]:
        sessions = await self.list_recent_sessions(limit=limit)
        targets: list[AIRecentTarget] = []
        seen_users: set[str] = set()
        seen_participants: set[str] = set()

        async with get_session() as session:
            for item in sessions:
                summary = (item.summary_text or "").strip()
                conversation_title = summary or item.session_id[:12]
                conversation_subtitle = (
                    f"{item.platform} · {item.scene_type} · {item.scene_id}"
                )
                targets.append(
                    AIRecentTarget(
                        target_type="scene",
                        anchor_type="scene",
                        anchor_id=item.session_id,
                        title=conversation_title,
                        subtitle=conversation_subtitle,
                        scene_id=item.session_id,
                        platform=item.platform,
                        scope_type=item.scene_type,
                        scope_id=item.scene_id,
                        user_id=item.subject_id,
                        last_active_at=item.last_message_at.isoformat(),
                    )
                )

                if item.scene_type == "group":
                    participant_user_ids = await (
                        chat_session_service.list_recent_user_ids_for_session(
                            session,
                            session_id=item.session_id,
                            limit=3,
                        )
                    )
                else:
                    participant_user_ids = [item.subject_id or item.scene_id]

                for user_id in participant_user_ids:
                    if not user_id:
                        continue
                    if item.scene_type == "group":
                        participant_id = build_participant_subject_id(
                            scene_type=item.scene_type,
                            scene_id=item.scene_id,
                            user_id=user_id,
                        )
                        if participant_id not in seen_participants:
                            seen_participants.add(participant_id)
                            targets.append(
                                AIRecentTarget(
                                    target_type="participant",
                                    anchor_type="participant",
                                    anchor_id=participant_id,
                                    title=user_id,
                                    subtitle=f"{item.platform} · group participant",
                                    scene_id=item.session_id,
                                    platform=item.platform,
                                    scope_type=item.scene_type,
                                    scope_id=item.scene_id,
                                    user_id=user_id,
                                    last_active_at=item.last_message_at.isoformat(),
                                )
                            )
                    if user_id in seen_users:
                        continue
                    seen_users.add(user_id)
                    user_subtitle = f"{item.platform} · {item.scene_type}"
                    targets.append(
                        AIRecentTarget(
                            target_type="user",
                            anchor_type="user",
                            anchor_id=user_id,
                            title=user_id,
                            subtitle=user_subtitle,
                            scene_id=item.session_id,
                            platform=item.platform,
                            scope_type=item.scene_type,
                            scope_id=item.scene_id,
                            user_id=user_id,
                            last_active_at=item.last_message_at.isoformat(),
                        )
                    )

        return targets[: limit * 2]

    async def list_scene_turns(
        self,
        *,
        scene_id: str,
        limit: int = 50,
    ) -> list["ChatMessageDetailView"]:
        async with get_session() as session:
            return await chat_session_service.list_messages_for_session(
                session,
                session_id=scene_id,
                limit=limit,
            )

    async def build_scene_prompt_preview(
        self,
        *,
        scene_id: str,
        turn_limit: int = 50,
    ) -> AISessionPromptPreview | None:
        async with get_session() as session:
            conversation = await chat_session_service.get_session_view(
                session,
                session_id=scene_id,
            )
            if conversation is None:
                return None
            identity = await chat_session_service.get_session_identity(
                session,
                session_id=scene_id,
            )
            if identity is None:
                return None
            turns = await chat_session_service.list_messages_for_session(
                session,
                session_id=scene_id,
                limit=turn_limit,
            )
            latest_user_turn = select_latest_user_turn(turns)
            latest_user_message = (
                latest_user_turn.text_content.strip()
                if latest_user_turn is not None
                else None
            )
            user_id = identity.subject_id or (
                latest_user_turn.author_id if latest_user_turn is not None else None
            )
            prompt_time = turns[-1].created_at if turns else datetime.now(timezone.utc)
            group_name = await _load_group_name(identity)
            relationship_context = None
            if user_id is not None:
                relationship_target = build_relationship_target(identity, user_id)
                relationship_context = await load_relationship_context(
                    session,
                    target=relationship_target,
                )
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=AIPersonaBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
                    user_id=user_id,
                ),
                render_context=build_persona_render_context(
                    bot_id=identity.bot_id,
                    current_time=prompt_time,
                    platform=identity.platform,
                    scene_type=identity.scene_type,
                    scene_id=identity.scene_id,
                    session_id=identity.session_id,
                    group_name=group_name,
                    user_id=user_id,
                    user_name=(
                        _find_recent_user_name(turns, user_id)
                        if user_id is not None
                        else None
                    )
                    or user_id,
                ),
            )
            tool_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
                session,
                scene_context=AIToolSceneContext(
                    scope_type=identity.scene_type,
                    is_tome=identity.scene_type == "private",
                ),
                target=AIToolPolicyBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
                    user_id=user_id,
                ),
            )
            memories = (
                await retrieve_memories_for_preview(
                    session,
                    identity=identity,
                    user_id=user_id,
                    query_text=latest_user_message or "",
                )
                if latest_user_message and user_id is not None
                else []
            )
            tool_results = extract_tool_result_lines(turns)
            tool_policy_text = summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                tool_policy,
            )
            person_profile = (
                await load_person_profile_for_prompt(
                    session,
                    identity=identity,
                    user_id=user_id,
                )
                if user_id is not None
                else ()
            )
            allowed_tools = ai_tool_service.list_allowed_tools(tool_policy)
            has_tools = bool(allowed_tools)
            pre_tool_task_class = select_pre_tool_reply_task_class(has_tools=has_tools)
            selected = await ai_model_facade.select_model(
                session,
                query=AIModelRouteQuery(task_class=pre_tool_task_class),
                target=AIModelBindingTarget(
                    conversation_id=identity.session_id,
                    group_id=(
                        identity.scene_id if identity.scene_type == "group" else None
                    ),
                    user_id=user_id,
                ),
            )
            roleplay_selected = (
                await ai_model_facade.select_model(
                    session,
                    query=AIModelRouteQuery(
                        task_class=select_post_tool_reply_task_class()
                    ),
                    target=AIModelBindingTarget(
                        conversation_id=identity.session_id,
                        group_id=(
                            identity.scene_id
                            if identity.scene_type == "group"
                            else None
                        ),
                        user_id=user_id,
                    ),
                )
                if has_tools
                else None
            )
            context_turns = to_context_turns(turns)
            social_decision = (
                await _evaluate_preview_social_judgment(
                    session,
                    judgment_input=_build_prompt_preview_social_input(
                        session_id=scene_id,
                        identity=identity,
                        latest_user_message=latest_user_message,
                        conversation_summary=conversation.summary_text,
                        relationship_context=relationship_context,
                        persona_id=persona.persona_id if persona is not None else None,
                        allowed_tool_names=tuple(tool.name for tool in allowed_tools),
                        context_turns=context_turns,
                    ),
                    target=AIModelBindingTarget(
                        conversation_id=identity.session_id,
                        group_id=(
                            identity.scene_id
                            if identity.scene_type == "group"
                            else None
                        ),
                        user_id=user_id,
                    ),
                )
                if latest_user_message
                else None
            )
            compose_input = AIRuntimeComposeInput(
                persona=persona,
                scene_type=identity.scene_type,
                person_profile=person_profile,
                relationship=relationship_context,
                tool_policy=tool_policy_text,
                tool_results=tool_results,
                memories=memories,
                conversation_summary=conversation.summary_text,
                social_policy_summary=(
                    summarize_reply_strategy_decision(social_decision)
                    if social_decision is not None
                    else None
                ),
                turns=context_turns,
            )
            planning_channels = (
                _to_prompt_channel_preview(
                    build_runtime_prompt_channels(
                        compose_input,
                        mode="planner" if has_tools else "roleplay",
                        include_tool_policy=has_tools,
                    )
                )
                if social_decision is None or social_decision.should_speak
                else AISessionPromptChannels(
                    mode="planner" if has_tools else "roleplay",
                    system_instructions=(),
                    persona="",
                    style=None,
                    relationship=None,
                    person_profile=(),
                    social_policy=None,
                    tool_policy=None,
                    future_task=None,
                    tool_results=(),
                    operator_memories=(),
                    summary_memories=(),
                    long_term_memories=(),
                    knowledge_memories=(),
                    conversation_summary=None,
                    context_priority=(),
                    conversation_messages=(),
                    response_rules=(),
                    instruction="Suppressed by social policy before prompt generation.",
                )
            )
            rendered_prompt = (
                compose_pre_tool_reply_prompt(
                    compose_input,
                    has_tools=has_tools,
                )
                if social_decision is None or social_decision.should_speak
                else "Suppressed by social policy before prompt generation."
            )
            roleplay_channels = (
                _to_prompt_channel_preview(
                    build_runtime_prompt_channels(
                        compose_input,
                        mode="roleplay",
                        include_tool_policy=False,
                    )
                )
                if has_tools
                and (social_decision is None or social_decision.should_speak)
                else None
            )
            rendered_roleplay_prompt = (
                compose_roleplay_reply_prompt(compose_input)
                if has_tools
                and (social_decision is None or social_decision.should_speak)
                else None
            )
            operator_memory_count = sum(
                1 for memory in memories if memory.memory_layer == "operator"
            )
            summary_memory_count = sum(
                1 for memory in memories if memory.memory_layer == "summary"
            )
            long_term_memory_count = sum(
                1 for memory in memories if memory.memory_layer == "long_term"
            )
            knowledge_memory_count = sum(
                1 for memory in memories if memory.memory_layer == "knowledge"
            )
            return AISessionPromptPreview(
                session_id=scene_id,
                latest_user_message=latest_user_message,
                planning_source_id=(
                    selected.source.source_id if selected is not None else None
                ),
                planning_profile_id=(
                    selected.profile.profile_id if selected is not None else None
                ),
                planning_model_name=(
                    selected.resolved_model_name if selected is not None else None
                ),
                planning_task_class=pre_tool_task_class,
                roleplay_source_id=(
                    roleplay_selected.source.source_id
                    if roleplay_selected is not None
                    else None
                ),
                roleplay_profile_id=(
                    roleplay_selected.profile.profile_id
                    if roleplay_selected is not None
                    else None
                ),
                roleplay_model_name=(
                    roleplay_selected.resolved_model_name
                    if roleplay_selected is not None
                    else None
                ),
                roleplay_task_class=(
                    select_post_tool_reply_task_class() if has_tools else None
                ),
                source_id=(selected.source.source_id if selected is not None else None),
                profile_id=(
                    selected.profile.profile_id if selected is not None else None
                ),
                model_name=(
                    selected.resolved_model_name if selected is not None else None
                ),
                persona_id=persona.persona_id if persona is not None else None,
                conversation_summary=conversation.summary_text,
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
                operator_memory_count=operator_memory_count,
                summary_memory_count=summary_memory_count,
                long_term_memory_count=long_term_memory_count,
                knowledge_memory_count=knowledge_memory_count,
                planning_channels=planning_channels,
                roleplay_channels=roleplay_channels,
                rendered_roleplay_prompt=(
                    rendered_roleplay_prompt if has_tools else None
                ),
                rendered_prompt=rendered_prompt,
            )



ai_admin_service = AIAdminService()

__all__ = ["AIAdminService", "ai_admin_service"]
