"""Default live runtime entry assembled from runtime-owned stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from nonebot.log import logger

from apeiria.ai.config import get_ai_plugin_config
from apeiria.ai.retention import ai_retention_service
from apeiria.ai.skills import ai_skill_service
from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.reply_strategy import build_wake_context
from apeiria.app.ai.reply_strategy.wake_gate import evaluate_wake
from apeiria.app.ai.runtime.composition import (
    create_session_runtime_resolver,
    create_session_turn_engine,
)
from apeiria.app.ai.runtime.context.memories import store_extracted_memories
from apeiria.app.ai.runtime.entry import (
    CommitResult,
    RuntimeTraceContext,
)
from apeiria.app.ai.runtime.session.context import (
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
    from apeiria.app.ai.runtime.session.runtime import (
        InMemoryAISessionRuntime,
        InMemoryAISessionRuntimeResolver,
    )
    from apeiria.app.ai.runtime.stages import RuntimeCommitResult
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True)
class AIRuntimeTurnRequest:
    """Normalized live runtime request shared by message and future-task ingress."""

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
        """Translate ingress request data into runtime-owned turn input."""

        return RuntimeTurnInput(
            identity=self.identity,
            source=RuntimeTurnSource(
                runtime_mode=self.runtime_mode,
                message_text=self.message_text,
                source_message_id=self.source_message_id,
                user_id=self.user_id,
                direct_signal=self.is_tome,
                is_private=self.identity.scene_type == "private",
                event_dedupe_key=self.event_dedupe_key,
                event_dedupe_claimed=self.event_dedupe_claimed,
            ),
            sender_id=self.sender_id,
            future_task=self.future_task,
            sentiment=self.sentiment,
        )


@dataclass(slots=True)
class DefaultAILiveRuntimeEntry:
    """Default runtime entry for live NoneBot messages and due future tasks."""

    session_runtime_resolver: InMemoryAISessionRuntimeResolver | None = None
    turn_engine: AISessionTurnEngine | None = None

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: RuntimeTraceContext | None = None,
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
        session_runtime = self._resolve_session_runtime(
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

        message_text = wake_context.message_text
        user_id = str(event.get_user_id())
        extraction_result = await store_extracted_memories(
            identity=identity,
            user_id=user_id,
            message_text=message_text,
            source_message_id=turn.message_id,
        )
        result = await self._run_turn(
            trace=trace
            or RuntimeTraceContext(kind="conversation", trigger="nonebot_message"),
            request=AIRuntimeTurnRequest(
                identity=identity,
                message_text=message_text,
                source_message_id=turn.message_id,
                user_id=user_id,
                sender_id=str(bot.self_id),
                runtime_mode="message",
                is_tome=bool(hasattr(event, "is_tome") and event.is_tome()),
                sentiment=extraction_result.sentiment,
                event_dedupe_key=event_dedupe_key,
                event_dedupe_claimed=event_dedupe_claimed,
            ),
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )
        return result.reply_text if result is not None else None

    async def handle_future_task(
        self,
        task_id: str,
        *,
        trace: RuntimeTraceContext | None = None,
    ) -> CommitResult | None:
        """Handle one due future task by running the normal reply runtime."""

        from apeiria.app.ai.future_tasks import ai_future_task_service

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
        legacy_commit = await self._run_turn(
            trace=trace
            or RuntimeTraceContext(kind="conversation", trigger="ai_future_task"),
            request=AIRuntimeTurnRequest(
                identity=identity,
                message_text=task.description,
                source_message_id=task.source_message_id,
                user_id=user_id,
                sender_id=identity.bot_id,
                runtime_mode="future_task",
                future_task=task,
                event_dedupe_key=task.source_message_id,
            ),
            current_time=datetime.now(timezone.utc),
            session_runtime=None,
        )
        if legacy_commit is None:
            return None
        return CommitResult(
            reply_text=legacy_commit.reply_text,
            commit_status=legacy_commit.commit_status,
            delivery_status=_delivery_status_for_commit(legacy_commit.delivery_result),
            substeps=legacy_commit.substeps,
            diagnostics=_delivery_diagnostics(legacy_commit.delivery_result),
        )

    async def _run_turn(
        self,
        *,
        trace: RuntimeTraceContext,
        request: AIRuntimeTurnRequest,
        current_time: datetime,
        wake_context: "WakeContext | None" = None,
        session_runtime: "InMemoryAISessionRuntime | None" = None,
    ) -> "RuntimeCommitResult | None":
        if session_runtime is None:
            session_runtime = self._resolve_session_runtime(
                request.identity.session_id,
                now=current_time,
            )
        return await self._resolve_turn_engine().run_reply_turn(
            trace_id=f"ai_trace_{uuid4().hex}",
            trace=trace,
            turn=request.to_runtime_turn_input(),
            session_runtime=session_runtime,
            wake_context=wake_context,
            current_time=current_time,
        )

    def _resolve_session_runtime(
        self,
        session_id: str,
        *,
        now: datetime,
    ) -> "InMemoryAISessionRuntime":
        resolver = self.session_runtime_resolver
        if resolver is None:
            resolver = create_session_runtime_resolver()
            object.__setattr__(self, "session_runtime_resolver", resolver)
        return resolver.resolve(session_id, now=now)

    def _resolve_turn_engine(self) -> AISessionTurnEngine:
        if self.turn_engine is not None:
            return self.turn_engine
        engine = create_session_turn_engine()
        object.__setattr__(self, "turn_engine", engine)
        return engine


def _message_event_dedupe_key(turn: Any) -> str | None:
    platform_message_id = getattr(turn, "platform_message_id", None)
    if isinstance(platform_message_id, str) and platform_message_id.strip():
        return f"platform_message:{platform_message_id.strip()}"

    source_message_id = getattr(turn, "message_id", None)
    if isinstance(source_message_id, str) and source_message_id.strip():
        return f"source_message:{source_message_id.strip()}"

    return None


def _delivery_status_for_commit(delivery_result: object | None) -> str | None:
    if delivery_result is None:
        return "not_required"
    delivered = getattr(delivery_result, "delivered", None)
    if delivered is True:
        return "committed"
    if delivered is False:
        return "failed"
    return None


def _delivery_diagnostics(delivery_result: object | None) -> dict[str, object]:
    if delivery_result is None:
        return {}
    diagnostics: dict[str, object] = {}
    for key in ("reason", "error", "status", "channel", "remote_message_id"):
        value = getattr(delivery_result, key, None)
        if value is not None:
            diagnostics[f"delivery_{key}"] = value
    if "delivery_reason" not in diagnostics and "delivery_error" in diagnostics:
        diagnostics["delivery_reason"] = diagnostics["delivery_error"]
    return diagnostics


__all__ = ["AIRuntimeTurnRequest", "DefaultAILiveRuntimeEntry"]
