"""Runtime service entrypoint for AI message handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.retention import ai_retention_service
from apeiria.ai.skills import ai_skill_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.pipeline.generation_steps import (
    DeliveryOutcome,
    gather_reply_inputs,
    generate_reply,
    prepare_generation,
)
from apeiria.app.ai.pipeline.memory_steps import store_extracted_memories
from apeiria.app.ai.pipeline.persistence_steps import persist_reply
from apeiria.app.ai.pipeline.reply_strategy_steps import decide_whether_to_speak
from apeiria.app.ai.reply_strategy import (
    build_wake_context,
    reply_strategy_service,
)
from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake
from apeiria.app.ai.tooling import ensure_app_ai_tools_loaded
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True, slots=True)
class AITraceContext:
    """Lightweight trace labels passed in from runtime/surface entrypoints."""

    kind: str
    trigger: str


_DEFAULT_MESSAGE_TRACE = AITraceContext(
    kind="conversation",
    trigger="nonebot_message",
)
_DEFAULT_FUTURE_TASK_TRACE = AITraceContext(
    kind="conversation",
    trigger="ai_future_task",
)


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
    delivery_result: DeliveryOutcome | None = None


class AIRuntimeService:
    """Minimal end-to-end runtime path for the AI plugin."""

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: AITraceContext | None = None,
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        ensure_app_ai_tools_loaded()
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

        ingested = await chat_session_service.ingest_event(
            bot,
            event,
            persist_raw_data=config.persist_raw_event_payloads,
        )
        if ingested is None:
            return None

        identity, turn = ingested
        user_id = str(event.get_user_id())
        is_tome = bool(hasattr(event, "is_tome") and event.is_tome())
        extraction_result = await store_extracted_memories(
            identity=identity,
            user_id=user_id,
            message_text=message_text,
            source_message_id=turn.message_id,
        )
        result = await self._run_reply_pipeline(
            trace_id=f"ai_trace_{uuid4().hex}",
            trace=trace or _DEFAULT_MESSAGE_TRACE,
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
        return result.reply_text if result is not None else None

    async def handle_future_task(
        self,
        task_id: str,
        *,
        trace: AITraceContext | None = None,
    ) -> AIRuntimeReplyResult | None:
        """Handle one due future task by running the normal reply pipeline."""

        ensure_app_ai_tools_loaded()
        ai_retention_service.maybe_schedule_cleanup(config=get_ai_plugin_config())
        task = await ai_future_task_service.get_task(task_id=task_id)
        if task is None or task.status != "running":
            return None

        identity = await chat_session_service.get_session_identity(
            session_id=task.session_id,
        )
        if identity is None:
            return None

        user_id = identity.subject_id or task.user_id or identity.scene_id
        return await self._run_reply_pipeline(
            trace_id=f"ai_trace_{uuid4().hex}",
            trace=trace or _DEFAULT_FUTURE_TASK_TRACE,
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

    async def _run_reply_pipeline(
        self,
        *,
        trace_id: str,
        trace: AITraceContext,
        request: AIRuntimeReplyRequest,
        wake_context: WakeContext | None = None,
    ) -> AIRuntimeReplyResult | None:
        current_time = datetime.now(timezone.utc)
        identity = request.identity

        inputs = await gather_reply_inputs(request, current_time)

        social_decision = await decide_whether_to_speak(
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
            return None
        prep = await prepare_generation(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
            trace_id=trace_id,
        )
        if prep is None:
            return None

        gen = await generate_reply(
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
                "AI trace {} skipped reply: empty model response for session {} "
                "entry_kind={} entry_trigger={}",
                trace_id,
                identity.session_id,
                trace.kind,
                trace.trigger,
            )
            return None

        await persist_reply(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            gen=gen,
            trace_id=trace_id,
        )
        # Only count as "replied" when the reply was actually delivered.
        # For regular messages delivery_result is None (plugin handler sends).
        # For future_tasks delivery happens internally and may fail.
        if gen.delivery_result is None or gen.delivery_result.delivered:
            reply_strategy_service.notify_replied(identity.session_id)
        logger.info(
            "AI trace {} generated {} reply for session {} with source={} "
            "model={} memories={} tool_observations={} entry_kind={} "
            "entry_trigger={}",
            trace_id,
            request.runtime_mode,
            identity.session_id,
            response.source_id,
            response.model_name,
            len(inputs.recalled_memories),
            len(gen.skill_runtime.turns),
            trace.kind,
            trace.trigger,
        )
        return AIRuntimeReplyResult(
            reply_text=response.content.strip(),
            delivery_result=gen.delivery_result,
        )


ai_runtime_service = AIRuntimeService()

__all__ = ["AIRuntimeService", "AITraceContext", "ai_runtime_service"]
