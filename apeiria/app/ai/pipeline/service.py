"""Runtime service entrypoint for AI message handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.retention import ai_retention_service
from apeiria.ai.skills import ai_skill_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.pipeline.context_window_steps import record_context_usage
from apeiria.app.ai.pipeline.delivery_steps import deliver_generated_reply
from apeiria.app.ai.pipeline.input_steps import gather_reply_inputs
from apeiria.app.ai.pipeline.memory_steps import store_extracted_memories
from apeiria.app.ai.pipeline.observation_steps import apply_reply_observation_effects
from apeiria.app.ai.pipeline.persistence_steps import AssistantReplyPersistenceStage
from apeiria.app.ai.pipeline.reply_strategy_steps import (
    decide_whether_to_speak,
)
from apeiria.app.ai.reply_strategy import (
    build_wake_context,
    reply_strategy_service,
)
from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake
from apeiria.app.ai.session_runtime import (
    AISessionTurnEngine,
    DefaultRuntimeCommitStage,
    DefaultRuntimeContextStage,
    DefaultRuntimeExecutionStage,
    DefaultRuntimeObservationStage,
    DefaultRuntimePlanningStage,
    DefaultRuntimePolicyStage,
    DefaultRuntimeTraceStage,
    InMemoryAISessionRuntimeResolver,
    RuntimeTurnInput,
    SessionRuntimePolicy,
)
from apeiria.app.ai.session_runtime.trace_store import turn_trace_repository
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
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
    event_dedupe_key: str | None = None
    event_dedupe_claimed: bool = False

    def to_runtime_turn_input(self) -> RuntimeTurnInput:
        """Translate ingress request data into the runtime-owned turn input."""

        return RuntimeTurnInput.from_reply_request(self)


@dataclass(frozen=True)
class AIRuntimeReplyResult:
    """Final runtime reply plus optional outbound delivery metadata."""

    reply_text: str
    delivery_result: DeliveryOutcome | None = None


class AIRuntimeService:
    """Minimal end-to-end runtime path for the AI plugin."""

    def __init__(
        self,
        *,
        session_runtime_resolver: Any | None = None,
        turn_engine: AISessionTurnEngine | None = None,
    ) -> None:
        if session_runtime_resolver is None:
            session_runtime_resolver = InMemoryAISessionRuntimeResolver(
                policy=SessionRuntimePolicy.from_config(get_ai_plugin_config())
            )
        self._session_runtime_resolver = session_runtime_resolver
        self._turn_engine = turn_engine

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: AITraceContext | None = None,
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        ensure_ai_runtime_support_initialized(source="runtime_fallback")
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
        event_dedupe_key = _message_event_dedupe_key(turn)
        current_time = datetime.now(timezone.utc)
        session_runtime = self._session_runtime_resolver.resolve(
            identity.session_id,
            now=current_time,
        )
        event_dedupe_claimed = False
        if event_dedupe_key is not None:
            event_dedupe_claimed = session_runtime.record_event_if_new(
                event_dedupe_key,
                now=current_time,
            )
            if not event_dedupe_claimed:
                logger.debug(
                    "AI skipped duplicate platform event for session {} key={}",
                    identity.session_id,
                    event_dedupe_key,
                )
                return None

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
                event_dedupe_key=event_dedupe_key,
                event_dedupe_claimed=event_dedupe_claimed,
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

        ensure_ai_runtime_support_initialized(source="runtime_fallback")
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
                event_dedupe_key=task.source_message_id,
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
        session_runtime = self._session_runtime_resolver.resolve(
            identity.session_id,
            now=current_time,
        )
        return await self._run_reply_pipeline_turn(
            trace_id=trace_id,
            trace=trace,
            request=request,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )

    async def _run_reply_pipeline_turn(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: AITraceContext,
        request: AIRuntimeReplyRequest,
        wake_context: WakeContext | None = None,
        current_time: datetime,
        session_runtime: Any | None = None,
    ) -> AIRuntimeReplyResult | None:
        commit = await self._resolve_turn_engine().run_reply_turn(
            trace_id=trace_id,
            trace=trace,
            turn=request.to_runtime_turn_input(),
            session_runtime=session_runtime,
            wake_context=wake_context,
            current_time=current_time,
        )
        if commit is None:
            return None
        return AIRuntimeReplyResult(
            reply_text=commit.reply_text,
            delivery_result=commit.delivery_result,
        )

    def _resolve_turn_engine(self) -> AISessionTurnEngine:
        if self._turn_engine is not None:
            return self._turn_engine
        return AISessionTurnEngine(
            policy_stage=DefaultRuntimePolicyStage(
                reply_decider=decide_whether_to_speak,
            ),
            observation_stage=DefaultRuntimeObservationStage(
                apply_observation_effects=apply_reply_observation_effects,
            ),
            context_stage=DefaultRuntimeContextStage(
                gather_reply_inputs=gather_reply_inputs,
            ),
            planning_stage=DefaultRuntimePlanningStage(),
            execution_stage=DefaultRuntimeExecutionStage(),
            commit_stage=DefaultRuntimeCommitStage(
                reply_persistence=AssistantReplyPersistenceStage(),
                reply_strategy_service=reply_strategy_service,
                deliver_reply=deliver_generated_reply,
                record_context_usage=record_context_usage,
            ),
            trace_stage=DefaultRuntimeTraceStage(trace_store=turn_trace_repository),
        )


def _message_event_dedupe_key(turn: Any) -> str | None:
    platform_message_id = getattr(turn, "platform_message_id", None)
    if isinstance(platform_message_id, str) and platform_message_id.strip():
        return f"platform_message:{platform_message_id.strip()}"

    source_message_id = getattr(turn, "message_id", None)
    if isinstance(source_message_id, str) and source_message_id.strip():
        return f"source_message:{source_message_id.strip()}"

    return None


ai_runtime_service = AIRuntimeService()

__all__ = ["AIRuntimeService", "AITraceContext", "ai_runtime_service"]
