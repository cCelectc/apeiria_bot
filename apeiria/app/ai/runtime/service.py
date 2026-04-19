"""Runtime service entrypoint for AI message handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from nonebot.log import logger
from nonebot_plugin_orm import get_session

from apeiria.app.ai.config import get_ai_plugin_config
from apeiria.app.ai.conversation.service import chat_session_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.reply_strategy import (
    build_wake_context,
    reply_strategy_service,
)
from apeiria.app.ai.reply_strategy.models import WakeContext
from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake
from apeiria.app.ai.retention import ai_retention_service
from apeiria.app.ai.runtime.generation_steps import (
    gather_reply_inputs,
    generate_reply,
    prepare_generation,
)
from apeiria.app.ai.runtime.memory_steps import store_extracted_memories
from apeiria.app.ai.runtime.observation import (
    build_future_task_observation,
    build_message_observation,
    finalize_observation,
)
from apeiria.app.ai.runtime.persistence_steps import persist_reply
from apeiria.app.ai.runtime.reply_strategy_steps import decide_whether_to_speak
from apeiria.app.ai.skills.service import ai_skill_service
from apeiria.app.runtime import SendResult

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ChatSessionIdentity
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.memory.models import AIMessageSentiment


@dataclass(frozen=True)
class AIRuntimeReplyRequest:
    """Normalized runtime request shared by message and future-task entrypoints."""

    identity: "ChatSessionIdentity"
    message_text: str
    source_message_id: str | None
    user_id: str
    sender_id: str
    runtime_mode: Literal["message", "future_task"]
    is_tome: bool = False
    future_task: "AIFutureTaskDefinition | None" = None
    sentiment: "AIMessageSentiment | None" = None


@dataclass(frozen=True)
class AIRuntimeReplyResult:
    """Final runtime reply plus optional outbound delivery metadata."""

    reply_text: str
    delivery_result: SendResult | None = None


class AIRuntimeService:
    """Minimal end-to-end runtime path for the AI plugin."""

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        ai_skill_service.ensure_initialized()
        config = get_ai_plugin_config()
        wake_context = build_wake_context(
            bot,
            event,
            allow_group_initiative=config.allow_group_initiative,
        )
        if wake_context is None:
            return None
        if not evaluate_wake(wake_context).should_process:
            return None
        message_text = wake_context.message_text
        ai_retention_service.maybe_schedule_cleanup(config=config)

        async with get_session() as session:
            ingested = await chat_session_service.ingest_event(
                session,
                bot,
                event,
                persist_raw_data=config.persist_raw_event_payloads,
            )
            if ingested is None:
                return None

            identity, turn = ingested
            user_id = str(event.get_user_id())
            is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
            observation = build_message_observation(
                identity,
                user_id=user_id,
                is_tome=is_tome,
            )
            try:
                extraction_result = await store_extracted_memories(
                    session,
                    identity=identity,
                    user_id=user_id,
                    message_text=message_text,
                    source_message_id=turn.message_id,
                )
                result = await self._run_reply_pipeline(
                    session,
                    trace_id=f"ai_trace_{uuid4().hex}",
                    request=AIRuntimeReplyRequest(
                        identity=identity,
                        message_text=message_text,
                        source_message_id=turn.message_id,
                        user_id=user_id,
                        sender_id=str(bot.self_id),
                        runtime_mode="message",
                        is_tome=is_tome,
                        sentiment=extraction_result.sentiment,
                    ),
                    wake_context=wake_context,
                )
            except Exception as exc:
                finalize_observation(observation, exception=exc)
                raise
            finalize_observation(
                observation,
                disposition="skipped" if result is None else "completed",
                note={"trace_id": f"ai_trace_{uuid4().hex[:8]}"},
            )
            return result.reply_text if result is not None else None

    async def handle_future_task(
        self,
        task_id: str,
    ) -> AIRuntimeReplyResult | None:
        """Handle one due future task by running the normal reply pipeline."""

        ai_retention_service.maybe_schedule_cleanup(config=get_ai_plugin_config())
        async with get_session() as session:
            task = await ai_future_task_service.get_task(session, task_id=task_id)
            if task is None or task.status != "running":
                return None

            identity = await chat_session_service.get_session_identity(
                session,
                session_id=task.session_id,
            )
            if identity is None:
                return None

            user_id = identity.subject_id or task.user_id or identity.scene_id
            observation = build_future_task_observation(
                identity,
                task=task,
                user_id=user_id,
            )
            try:
                result = await self._run_reply_pipeline(
                    session,
                    trace_id=f"ai_trace_{uuid4().hex}",
                    request=AIRuntimeReplyRequest(
                        identity=identity,
                        message_text=task.description,
                        source_message_id=task.source_message_id,
                        user_id=user_id,
                        sender_id=identity.bot_id,
                        runtime_mode="future_task",
                        future_task=task,
                    ),
                )
            except Exception as exc:
                finalize_observation(observation, exception=exc)
                raise
            finalize_observation(
                observation,
                disposition="skipped" if result is None else "completed",
                note={
                    "task_id": task.task_id,
                    "delivery_channel": (
                        result.delivery_result.channel
                        if result and result.delivery_result
                        else None
                    ),
                },
            )
            return result

    async def _run_reply_pipeline(
        self,
        session: "AsyncSession",
        *,
        trace_id: str,
        request: AIRuntimeReplyRequest,
        wake_context: WakeContext | None = None,
    ) -> AIRuntimeReplyResult | None:
        current_time = datetime.now(timezone.utc)
        identity = request.identity

        inputs = await gather_reply_inputs(session, request, current_time)

        social_decision = await decide_whether_to_speak(
            session,
            request=request,
            wake_context=wake_context,
            turns=inputs.turns,
            conversation_summary=inputs.conversation_summary,
            relationship_context=inputs.relationship_context,
            persona=inputs.persona,
            allowed_tools=inputs.allowed_tools,
            initiative_bias=inputs.initiative_bias,
            model_target=inputs.model_target,
            current_time=current_time,
            trace_id=trace_id,
        )
        if not social_decision.should_speak:
            await session.commit()
            return None
        prep = await prepare_generation(
            session,
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
            trace_id=trace_id,
        )
        if prep is None:
            return None

        gen = await generate_reply(
            session,
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            current_time=current_time,
            trace_id=trace_id,
        )
        response = gen.response
        if response is None or not response.content.strip():
            logger.debug(
                "AI trace {} skipped reply: empty model response for session {}",
                trace_id,
                identity.session_id,
            )
            return None

        await persist_reply(
            session,
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            gen=gen,
            trace_id=trace_id,
        )
        await session.commit()
        # Only count as "replied" when the reply was actually delivered.
        # For regular messages delivery_result is None (plugin handler sends).
        # For future_tasks delivery happens internally and may fail.
        if gen.delivery_result is None or gen.delivery_result.delivered:
            reply_strategy_service.notify_replied(identity.session_id)
        logger.info(
            "AI trace {} generated {} reply for session {} with source={} "
            "model={} memories={} tool_observations={}",
            trace_id,
            request.runtime_mode,
            identity.session_id,
            response.source_id,
            response.model_name,
            len(inputs.recalled_memories),
            len(gen.skill_runtime.turns),
        )
        return AIRuntimeReplyResult(
            reply_text=response.content.strip(),
            delivery_result=gen.delivery_result,
        )

ai_runtime_service = AIRuntimeService()

__all__ = ["AIRuntimeService", "ai_runtime_service"]
