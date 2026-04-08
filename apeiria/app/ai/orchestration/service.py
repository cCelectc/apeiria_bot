"""Minimal working orchestration loop for AI replies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger
from nonebot_plugin_orm import get_session

from apeiria.app.ai.context.service import AITurnCreate, ai_context_service
from apeiria.app.ai.models.bindings import AIModelBindingTarget
from apeiria.app.ai.models.client import ai_model_client
from apeiria.app.ai.models.factory import build_provider_adapter
from apeiria.app.ai.models.models import AIModelRouteQuery
from apeiria.app.ai.models.provider import AIModelGenerateRequest
from apeiria.app.ai.models.service import ai_model_service
from apeiria.app.ai.persona.models import AIPersonaBindingTarget
from apeiria.app.ai.persona.service import ai_persona_service
from apeiria.app.ai.providers.service import ai_provider_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.app.ai.context.models import AIContextTurnView, AIConversationIdentity
    from apeiria.app.ai.models.selection import AISelectedModel
    from apeiria.app.ai.persona.service import AIPersonaPromptBundle


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


def _format_turn(turn: AIContextTurnView) -> str:
    speaker_map = {
        "user": "User",
        "bot": "Assistant",
        "system": "System",
        "tool": "Tool",
    }
    return f"{speaker_map.get(turn.sender_type, 'Message')}: {turn.content_text}"


def _render_turns(turns: list[AIContextTurnView]) -> str:
    if not turns:
        return "User: <empty>"
    return "\n".join(_format_turn(turn) for turn in turns if turn.content_text.strip())


def _build_prompt(
    persona: "AIPersonaPromptBundle | None",
    turns: list[AIContextTurnView],
) -> str:
    sections: list[str] = []
    if persona is not None:
        sections.append(f"[Persona]\n{persona.system_prompt}")
        if persona.style_prompt:
            sections.append(f"[Style]\n{persona.style_prompt}")
    else:
        sections.append("[Persona]\nYou are a helpful social AI in a chat.")
    sections.append(f"[Conversation]\n{_render_turns(turns)}")
    sections.append(
        "[Instruction]\n"
        "Reply naturally as the assistant in the same conversation. "
        "Keep the answer grounded in the visible conversation context."
    )
    return "\n\n".join(sections)


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
        if not _extract_plaintext(event):
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
                        prompt=_build_prompt(persona, turns),
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
