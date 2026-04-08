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

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.context.models import AIConversationIdentity
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.models.selection import AISelectedModel


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
    return recalled[:4]


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
            persona_target = _to_persona_target(identity, user_id)
            model_target = _to_model_target(identity, user_id)
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=persona_target,
            )
            recalled_memories = await _recall_memories(
                session,
                identity=identity,
                user_id=user_id,
                query_text=message_text,
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
