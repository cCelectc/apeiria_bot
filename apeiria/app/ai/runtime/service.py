"""Runtime service entrypoint for AI message handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger
from nonebot_plugin_orm import get_session

from apeiria.app.ai.conversation.service import (
    AITurnCreate,
    ai_conversation_service,
)
from apeiria.app.ai.decision.service import ai_decision_service
from apeiria.app.ai.model import AIModelBindingTarget, AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.runtime.composer import (
    AIRuntimeComposeInput,
    compose_reply_prompt,
)
from apeiria.app.ai.runtime.memory_steps import (
    recall_memories,
    store_extracted_memories,
)
from apeiria.app.ai.runtime.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
    update_relationship_state,
)
from apeiria.app.ai.skills.policy import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
)
from apeiria.app.ai.skills.service import AISkillRuntimeRequest, ai_skill_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import AIConversationIdentity
    from apeiria.app.ai.skills.policy import AIToolPolicy, AIToolTurnCreateInput


def _to_persona_target(
    identity: "AIConversationIdentity",
    user_id: str,
) -> AIPersonaBindingTarget:
    return AIPersonaBindingTarget(
        conversation_id=identity.conversation_id,
        group_id=identity.scope_id if identity.scope_type == "group" else None,
        user_id=identity.subject_user_id or user_id,
    )


def _to_model_target(
    identity: "AIConversationIdentity",
    user_id: str,
) -> AIModelBindingTarget:
    return AIModelBindingTarget(
        conversation_id=identity.conversation_id,
        group_id=identity.scope_id if identity.scope_type == "group" else None,
        user_id=identity.subject_user_id or user_id,
    )


async def _resolve_tool_policy(
    session: "AsyncSession",
    identity: "AIConversationIdentity",
    *,
    is_tome: bool,
) -> "AIToolPolicy":
    return await ai_tool_policy_binding_service.resolve_scene_policy(
        session,
        scene_context=AIToolSceneContext(
            scope_type=identity.scope_type,
            is_tome=is_tome,
        ),
        target=AIToolPolicyBindingTarget(
            conversation_id=identity.conversation_id,
            group_id=identity.scope_id if identity.scope_type == "group" else None,
            user_id=identity.subject_user_id,
        ),
    )


async def _append_tool_observation_turns(
    session: "AsyncSession",
    *,
    identity: "AIConversationIdentity",
    tool_turns: tuple["AIToolTurnCreateInput", ...],
) -> None:
    for index, turn in enumerate(tool_turns):
        await ai_conversation_service.append_turn(
            session,
            identity,
            AITurnCreate(
                sender_type="tool",
                sender_id=turn.sender_id,
                content_text=turn.content_text,
                raw_payload={
                    "index": index,
                    **turn.raw_payload,
                },
            ),
        )


class AIRuntimeService:
    """Minimal end-to-end runtime path for the AI plugin."""

    async def handle_message(  # noqa: PLR0911
        self,
        bot: "Bot",
        event: "Event",
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        decision_payload = ai_decision_service.decide_for_event(bot, event)
        if decision_payload is None:
            return None
        decision, message_text = decision_payload
        if not decision.should_reply:
            return None
        user_id = str(event.get_user_id())

        async with get_session() as session:
            ingested = await ai_conversation_service.ingest_event(session, bot, event)
            if ingested is None:
                return None

            identity, turn = ingested
            is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
            await store_extracted_memories(
                session,
                identity=identity,
                user_id=user_id,
                message_text=message_text,
                source_turn_id=turn.turn_id,
            )
            turns = await ai_conversation_service.list_recent_turns(
                session,
                identity,
                max_turns=8,
            )
            relationship_target = build_relationship_target(identity, user_id)
            persona_target = _to_persona_target(identity, user_id)
            model_target = _to_model_target(identity, user_id)
            tool_policy = await _resolve_tool_policy(
                session,
                identity,
                is_tome=is_tome,
            )
            persona = await ai_persona_service.build_persona_prompt_bundle(
                session,
                target=persona_target,
            )
            await update_relationship_state(
                session,
                target=relationship_target,
                message_text=message_text,
                is_tome=is_tome,
            )
            recalled_memories = await recall_memories(
                session,
                identity=identity,
                user_id=user_id,
                query_text=message_text,
            )
            relationship_context = await load_relationship_context(
                session,
                target=relationship_target,
            )
            skill_runtime = await ai_skill_service.run_for_message(
                session,
                AISkillRuntimeRequest(
                    conversation_id=identity.conversation_id,
                    message_text=message_text,
                    policy=tool_policy,
                    recalled_memories=tuple(recalled_memories),
                    relationship_context=relationship_context,
                ),
            )
            await _append_tool_observation_turns(
                session,
                identity=identity,
                tool_turns=skill_runtime.turns,
            )
            selected = await ai_model_facade.select_model(
                session,
                query=AIModelRouteQuery(task_class="reply_default"),
                target=model_target,
            )
            await session.commit()
            if selected is None:
                return None

            try:
                response = await ai_model_facade.generate_text(
                    selected,
                    prompt=compose_reply_prompt(
                        AIRuntimeComposeInput(
                            persona=persona,
                            relationship=relationship_context,
                            skill_policy=skill_runtime.policy_text,
                            skill_results=skill_runtime.result_lines,
                            memories=recalled_memories,
                            turns=turns,
                        )
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.opt(exception=exc).warning(
                    "AI reply generation failed for conversation {}",
                    identity.conversation_id,
                )
                return None

            if response is None or not response.content.strip():
                return None

            await ai_conversation_service.append_turn(
                session,
                identity,
                AITurnCreate(
                    sender_type="bot",
                    sender_id=str(bot.self_id),
                    content_text=response.content.strip(),
                    raw_payload={
                        "provider_id": response.provider_id,
                        "model_name": response.model_name,
                    },
                ),
            )
            await session.commit()
            return response.content.strip()


ai_runtime_service = AIRuntimeService()

__all__ = ["AIRuntimeService", "ai_runtime_service"]
