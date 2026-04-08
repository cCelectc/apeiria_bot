"""Minimal working orchestration loop for AI replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger
from nonebot_plugin_orm import get_session

from apeiria.app.ai.context.service import AITurnCreate, ai_context_service
from apeiria.app.ai.memory.models import AIMemoryQuery
from apeiria.app.ai.memory.service import ai_memory_service
from apeiria.app.ai.models.bindings import AIModelBindingTarget
from apeiria.app.ai.models.client import ai_model_client
from apeiria.app.ai.models.factory import build_provider_adapter
from apeiria.app.ai.models.models import AIModelRouteQuery
from apeiria.app.ai.models.provider import AIModelGenerateRequest
from apeiria.app.ai.models.service import ai_model_service
from apeiria.app.ai.orchestration.prompting import (
    build_reply_prompt_channels,
    render_reply_prompt,
)
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.providers.service import ai_provider_service
from apeiria.app.ai.relationship.scoring import project_emotion
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.app.ai.relationship.signals import derive_relationship_delta

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.context.models import AIConversationIdentity
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.models.selection import AISelectedModel
    from apeiria.app.ai.relationship.models import AIRelationshipState


def _is_private_like_event(event: Event, user_id: str) -> bool:
    session_id = getattr(event, "get_session_id", lambda: "")()
    return session_id == user_id


def _should_handle_event(bot: Bot, event: Event, user_id: str) -> bool:
    if str(user_id) == str(bot.self_id):
        return False
    if hasattr(event, "is_tome") and event.is_tome():
        return True
    return _is_private_like_event(event, user_id)


def _extract_plaintext(event: Event) -> str:
    try:
        return event.get_plaintext().strip()
    except Exception:  # noqa: BLE001
        return ""


def _to_persona_target(
    identity: AIConversationIdentity,
    user_id: str,
) -> AIPersonaBindingTarget:
    return AIPersonaBindingTarget(
        conversation_id=identity.conversation_id,
        group_id=identity.scope_id if identity.scope_type == "group" else None,
        user_id=identity.subject_user_id or user_id,
    )


def _to_model_target(
    identity: AIConversationIdentity,
    user_id: str,
) -> AIModelBindingTarget:
    return AIModelBindingTarget(
        conversation_id=identity.conversation_id,
        group_id=identity.scope_id if identity.scope_type == "group" else None,
        user_id=identity.subject_user_id or user_id,
    )


@dataclass(frozen=True)
class AIMemoryRecallTarget:
    """One memory retrieval boundary for reply orchestration."""

    subject_type: str
    subject_id: str


@dataclass(frozen=True)
class AIRelationshipTarget:
    """Resolved relationship target for one incoming user message."""

    platform: str
    group_id: str | None
    user_id: str
    is_private: bool


_MEMORY_TYPE_LIMITS: dict[str, int] = {
    "preference": 2,
    "relationship": 1,
    "episode": 1,
    "fact": 1,
    "summary": 1,
    "operator_note": 1,
}
_MAX_RECALLED_MEMORIES = 4


def _build_memory_targets(
    identity: AIConversationIdentity,
    user_id: str,
) -> list[AIMemoryRecallTarget]:
    targets = [
        AIMemoryRecallTarget(
            subject_type="conversation",
            subject_id=identity.conversation_id,
        )
    ]
    effective_user_id = identity.subject_user_id or user_id
    if effective_user_id:
        targets.append(
            AIMemoryRecallTarget(
                subject_type="user",
                subject_id=effective_user_id,
            )
        )
    return targets


def _apply_memory_budget(
    memories: list["AIMemoryDefinition"],
) -> list["AIMemoryDefinition"]:
    selected: list[AIMemoryDefinition] = []
    selected_ids: set[str] = set()
    type_counts: dict[str, int] = {}

    for memory in memories:
        type_limit = _MEMORY_TYPE_LIMITS.get(memory.memory_type, 1)
        if type_counts.get(memory.memory_type, 0) >= type_limit:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        type_counts[memory.memory_type] = type_counts.get(memory.memory_type, 0) + 1
        if len(selected) >= _MAX_RECALLED_MEMORIES:
            return selected

    for memory in memories:
        if memory.memory_id in selected_ids:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        if len(selected) >= _MAX_RECALLED_MEMORIES:
            break
    return selected


def _build_relationship_target(
    identity: AIConversationIdentity,
    user_id: str,
) -> AIRelationshipTarget:
    return AIRelationshipTarget(
        platform=identity.platform,
        group_id=identity.scope_id if identity.scope_type == "group" else None,
        user_id=identity.subject_user_id or user_id,
        is_private=identity.scope_type == "private",
    )


def _format_relationship_context(
    state: "AIRelationshipState",
) -> str | None:
    projection = project_emotion(state)
    mood_part = (
        f"Recent mood tags: {', '.join(state.mood_tags)}."
        if state.mood_tags
        else "Recent mood tags: none."
    )
    return (
        f"Current affinity score toward this user: {state.score:.2f}. "
        f"Projected tone: {projection.tone}. "
        f"Warmth bias: {projection.warmth_bias:.2f}. "
        f"Initiative bias: {projection.initiative_bias:.2f}. "
        f"{mood_part}"
    )


def _build_tool_policy_context() -> str:
    return (
        "No external tool execution is enabled in this reply path. "
        "Do not claim to have performed actions outside the visible chat context."
    )


async def _recall_memories(
    session: AsyncSession,
    *,
    identity: AIConversationIdentity,
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    recalled: list[AIMemoryDefinition] = []
    seen_ids: set[str] = set()
    for target in _build_memory_targets(identity, user_id):
        rows = await ai_memory_service.recall_memories(
            session,
            AIMemoryQuery(
                subject_type=target.subject_type,
                subject_id=target.subject_id,
                query_text=query_text,
                limit=3,
            ),
        )
        for row in rows:
            if row.memory_id in seen_ids:
                continue
            seen_ids.add(row.memory_id)
            recalled.append(row)
    return _apply_memory_budget(recalled)


async def _load_relationship_context(
    session: AsyncSession,
    *,
    target: AIRelationshipTarget,
) -> str | None:
    state = await ai_relationship_service.get_state(
        session,
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
    )
    return _format_relationship_context(state)


async def _update_relationship_state(
    session: AsyncSession,
    *,
    target: AIRelationshipTarget,
    message_text: str,
    is_tome: bool,
) -> None:
    delta = derive_relationship_delta(
        text=message_text,
        is_private=target.is_private,
        is_tome=is_tome,
    )
    if delta is None:
        return

    await ai_relationship_service.apply_delta(
        session,
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
        delta=delta,
    )


def _resolve_model_name(selected: AISelectedModel) -> str | None:
    model_name = selected.profile.model_name.strip()
    if model_name:
        return model_name
    default_model = selected.provider.default_model
    if isinstance(default_model, str) and default_model.strip():
        return default_model.strip()
    return None


class AIOrchestrationService:
    """Minimal end-to-end reply path for the AI plugin."""

    async def handle_message(  # noqa: PLR0911
        self,
        bot: Bot,
        event: Event,
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        try:
            user_id = str(event.get_user_id())
        except Exception:  # noqa: BLE001
            return None
        if not _should_handle_event(bot, event, user_id):
            return None
        message_text = _extract_plaintext(event)
        if not message_text:
            return None

        async with get_session() as session:
            ingested = await ai_context_service.ingest_event(session, bot, event)
            if ingested is None:
                return None

            identity, _turn = ingested
            turns = await ai_context_service.list_recent_turns(
                session,
                identity,
                max_turns=8,
            )
            relationship_target = _build_relationship_target(identity, user_id)
            persona_target = _to_persona_target(identity, user_id)
            model_target = _to_model_target(identity, user_id)
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=persona_target,
            )
            await _update_relationship_state(
                session,
                target=relationship_target,
                message_text=message_text,
                is_tome=bool(hasattr(event, "is_tome") and event.is_tome()),
            )
            recalled_memories = await _recall_memories(
                session,
                identity=identity,
                user_id=user_id,
                query_text=message_text,
            )
            relationship_context = await _load_relationship_context(
                session,
                target=relationship_target,
            )
            selected = await ai_model_service.select_model(
                session,
                query=AIModelRouteQuery(task_class="reply_default"),
                target=model_target,
            )
            await session.commit()
            if selected is None:
                return None

            provider = selected.provider
            api_key = ai_provider_service.get_provider_api_key(provider)
            model_name = _resolve_model_name(selected)
            if not api_key or not model_name:
                return None

            ai_model_client.registry.register(
                provider.provider_id,
                build_provider_adapter(provider, api_key=api_key),
            )

            try:
                response = await ai_model_client.generate_text(
                    AIModelGenerateRequest(
                        provider_id=provider.provider_id,
                        model_name=model_name,
                        prompt=render_reply_prompt(
                            build_reply_prompt_channels(
                                persona=persona,
                                relationship=relationship_context,
                                tool_policy=_build_tool_policy_context(),
                                memories=recalled_memories,
                                turns=turns,
                            )
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.opt(exception=exc).warning(
                    "AI reply generation failed for conversation {}",
                    identity.conversation_id,
                )
                return None

            if not response.content.strip():
                return None

            await ai_context_service.append_turn(
                session,
                identity,
                AITurnCreate(
                    sender_type="bot",
                    sender_id=str(bot.self_id),
                    content_text=response.content.strip(),
                    raw_payload={
                        "provider_id": provider.provider_id,
                        "model_name": model_name,
                    },
                ),
            )
            await session.commit()
            return response.content.strip()


ai_orchestration_service = AIOrchestrationService()
