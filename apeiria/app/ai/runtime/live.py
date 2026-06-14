"""Default live runtime entry assembled from runtime-owned stages."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from nonebot.log import logger

from apeiria.ai.runtime_settings import ai_runtime_settings_service
from apeiria.app.ai.lifecycle import ensure_ai_runtime_support_initialized
from apeiria.app.ai.reply_strategy.wake_gate import build_wake_context, evaluate_wake
from apeiria.app.ai.runtime.composition import (
    create_ai_runtime_coordinator,
    create_session_runtime_resolver,
)
from apeiria.app.ai.runtime.contracts import (
    FutureTaskRuntimeResult,
    RuntimeTraceContext,
)
from apeiria.app.ai.runtime.orchestrator import ReplyRuntimeRequest
from apeiria.app.ai.runtime.session.context import (
    RuntimeMediaDiagnostic,
    RuntimeSourceMediaKind,
    RuntimeSourceMediaPart,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.session.runtime import SessionRuntimePolicy
from apeiria.app.ai.runtime.speech import speech_input_preparer
from apeiria.app.ai.wiring import ai_wiring
from apeiria.app.chat.connection import WebChatConnectionClosed
from apeiria.app.chat.protocol import (
    PartialReplyCompletePayload,
    PartialReplyDeltaPayload,
    PartialReplyFailedPayload,
    PartialReplyStartPayload,
)
from apeiria.bot.ingest import build_ingested_chat_event
from apeiria.bot.live_context import live_platform_context
from apeiria.conversation.contracts import ChatMessageCreate
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.orchestrator import (
        AIRuntimeCoordinator,
        AIRuntimeResult,
    )
    from apeiria.app.ai.runtime.session.runtime import (
        InMemoryAISessionRuntime,
        InMemoryAISessionRuntimeResolver,
    )
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True)
class AIRuntimeIngressRequest:
    """Normalized live ingress data before coordinator request construction."""

    identity: "ChatSessionIdentity"
    message_text: str
    source_message_id: str | None
    user_id: str
    sender_id: str
    runtime_mode: Literal["message", "future_task"]
    is_tome: bool = False
    reply_to_bot: bool = False
    future_task: "AIFutureTaskDefinition | None" = None
    sentiment: "AIMessageSentiment | None" = None
    event_dedupe_key: str | None = None
    event_dedupe_claimed: bool = False
    media_parts: tuple[RuntimeSourceMediaPart, ...] = ()
    media_diagnostics: tuple[RuntimeMediaDiagnostic, ...] = ()
    speech_diagnostics: tuple[dict[str, object], ...] = ()
    stream_sink: Any | None = None

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
                reply_to_bot=self.reply_to_bot,
                event_dedupe_key=self.event_dedupe_key,
                event_dedupe_claimed=self.event_dedupe_claimed,
                media_parts=self.media_parts,
                media_diagnostics=self.media_diagnostics,
                speech_diagnostics=self.speech_diagnostics,
            ),
            sender_id=self.sender_id,
            future_task=self.future_task,
            sentiment=self.sentiment,
            stream_sink=self.stream_sink,
        )


@dataclass(slots=True)
class DefaultAILiveRuntimeEntry:
    """Default runtime entry for live NoneBot messages and due future tasks."""

    session_runtime_resolver: InMemoryAISessionRuntimeResolver | None = None
    coordinator: AIRuntimeCoordinator | None = None

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: RuntimeTraceContext | None = None,
    ) -> str | None:
        """Handle one runtime message and optionally return a reply."""

        ensure_ai_runtime_support_initialized(source="runtime_fallback")
        settings = await ai_runtime_settings_service.get_settings()
        wake_context = build_wake_context(
            bot,
            event,
            allow_group_initiative=settings.allow_group_initiative,
        )
        if wake_context is None:
            return None
        if not evaluate_wake(wake_context).should_process:
            return None

        ai_wiring.retention_service.maybe_schedule_cleanup(settings=settings)
        ingested = build_ingested_chat_event(
            bot,
            event,
            persist_raw_data=settings.persist_raw_event_payloads,
        )
        if ingested is None:
            return None

        identity = ingested.identity
        turn = await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="user",
                author_id=ingested.author_id,
                author_name=ingested.author_name,
                text_content=ingested.text_content,
                message_kind=ingested.message_kind,
                directed_to_bot=ingested.directed_to_bot,
                mentions_bot=ingested.mentions_bot,
                has_media=ingested.has_media,
                platform_message_id=ingested.platform_message_id,
                platform_reply_id=ingested.platform_reply_id,
                content=ingested.content,
                raw_data=ingested.raw_data,
            ),
        )
        event_dedupe_key = _message_event_dedupe_key(turn)
        current_time = datetime.now(timezone.utc)
        session_runtime = await self._resolve_session_runtime(
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
        media = extract_runtime_media(getattr(turn, "content_json", None))
        reply_to_bot = await _is_reply_to_bot_message(
            session_id=identity.session_id,
            platform_reply_id=ingested.platform_reply_id,
            bot_self_id=str(bot.self_id),
        )
        with live_platform_context(bot=bot, event=event):
            result = await self._run_turn(
                trace=trace
                or RuntimeTraceContext(kind="conversation", trigger="nonebot_message"),
                request=AIRuntimeIngressRequest(
                    identity=identity,
                    message_text=message_text,
                    source_message_id=turn.message_id,
                    user_id=user_id,
                    sender_id=str(bot.self_id),
                    runtime_mode="message",
                    is_tome=bool(hasattr(event, "is_tome") and event.is_tome()),
                    reply_to_bot=reply_to_bot,
                    event_dedupe_key=event_dedupe_key,
                    event_dedupe_claimed=event_dedupe_claimed,
                    media_parts=media.parts,
                    media_diagnostics=media.diagnostics,
                    stream_sink=_webchat_stream_sink(
                        bot=bot,
                        session_id=identity.session_id,
                    ),
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
    ) -> FutureTaskRuntimeResult | None:
        """Handle one due future task by running the normal reply runtime."""

        from apeiria.app.ai.future_tasks import ai_future_task_service

        ensure_ai_runtime_support_initialized(source="runtime_fallback")
        ai_wiring.retention_service.maybe_schedule_cleanup(
            settings=await ai_runtime_settings_service.get_settings()
        )
        task = await ai_future_task_service.get_task(task_id=task_id)
        if task is None or task.status != "running":
            return None

        identity = await chat_session_service.get_session_identity(
            session_id=task.session_id,
        )
        if identity is None:
            return None

        user_id = identity.subject_id or task.user_id or identity.scene_id
        runtime_result = await self._run_turn(
            trace=trace
            or RuntimeTraceContext(kind="conversation", trigger="ai_future_task"),
            request=AIRuntimeIngressRequest(
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
        if runtime_result is None or runtime_result.commit is None:
            return None
        runtime_commit = runtime_result.commit
        return FutureTaskRuntimeResult(
            reply_text=runtime_commit.reply_text,
            commit_status=runtime_commit.commit_status,
            delivery_status=_delivery_status_for_commit(runtime_commit.delivery_result),
            substeps=runtime_commit.substeps,
            diagnostics=_delivery_diagnostics(runtime_commit.delivery_result),
        )

    async def _run_turn(
        self,
        *,
        trace: RuntimeTraceContext,
        request: AIRuntimeIngressRequest,
        current_time: datetime,
        wake_context: "WakeContext | None" = None,
        session_runtime: "InMemoryAISessionRuntime | None" = None,
    ) -> "AIRuntimeResult | None":
        if session_runtime is None:
            session_runtime = await self._resolve_session_runtime(
                request.identity.session_id,
                now=current_time,
            )
        trace_id = f"ai_trace_{uuid4().hex}"
        if request.stream_sink is not None:
            request = replace(
                request,
                stream_sink=_stream_sink_with_trace_id(
                    request.stream_sink,
                    trace_id=trace_id,
                ),
            )
        turn = request.to_runtime_turn_input()
        settings = await ai_runtime_settings_service.get_settings()
        if settings.stt_input_enabled:
            speech = await speech_input_preparer.prepare(turn, settings=settings)
            turn = speech.turn
        return await self._resolve_coordinator().run(
            ReplyRuntimeRequest(
                trace_id=trace_id,
                trace=trace,
                turn=turn,
                session_runtime=session_runtime,
                wake_context=wake_context,
                current_time=current_time,
            )
        )

    async def _resolve_session_runtime(
        self,
        session_id: str,
        *,
        now: datetime,
    ) -> "InMemoryAISessionRuntime":
        settings = await ai_runtime_settings_service.get_settings()
        resolver = self.session_runtime_resolver
        if resolver is None:
            resolver = await create_session_runtime_resolver()
            object.__setattr__(self, "session_runtime_resolver", resolver)
        return resolver.resolve(
            session_id,
            now=now,
            policy=SessionRuntimePolicy.from_settings(settings),
        )

    def _resolve_coordinator(self) -> AIRuntimeCoordinator:
        if self.coordinator is not None:
            return self.coordinator
        coordinator = create_ai_runtime_coordinator()
        object.__setattr__(self, "coordinator", coordinator)
        return coordinator


def _message_event_dedupe_key(turn: Any) -> str | None:
    platform_message_id = getattr(turn, "platform_message_id", None)
    if isinstance(platform_message_id, str) and platform_message_id.strip():
        return f"platform_message:{platform_message_id.strip()}"

    source_message_id = getattr(turn, "message_id", None)
    if isinstance(source_message_id, str) and source_message_id.strip():
        return f"source_message:{source_message_id.strip()}"

    return None


async def _is_reply_to_bot_message(
    *,
    session_id: str,
    platform_reply_id: str | None,
    bot_self_id: str,
) -> bool:
    if not platform_reply_id:
        return False
    replied = await chat_session_service.get_message_by_platform_message_id(
        session_id=session_id,
        platform_message_id=platform_reply_id,
    )
    if replied is None:
        return False
    return replied.author_role == "assistant" or replied.author_id == bot_self_id


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


def _webchat_stream_sink(
    *,
    bot: object,
    session_id: str,
) -> object | None:
    connection = getattr(bot, "_connection", None)
    emitter = getattr(bot, "_emitter", None)
    if connection is None or emitter is None:
        return None

    def publish(event: object, *, trace_id: str | None = None) -> None:
        import asyncio

        frame = _partial_reply_payload_from_stream_event(
            event,
            session_id=session_id,
            trace_id=trace_id,
        )
        if frame is None:
            return
        method_name, payload = frame
        method = getattr(emitter, method_name, None)
        if method is None:
            return
        task = asyncio.create_task(method(connection, payload))
        task.add_done_callback(_discard_completed_partial_reply_task)

    return publish


def _discard_completed_partial_reply_task(task: object) -> None:
    try:
        exc = task.exception()
    except Exception:  # noqa: BLE001
        return
    if exc is None or isinstance(exc, WebChatConnectionClosed):
        return
    logger.opt(exception=exc).warning("Web UI chat partial reply emission failed")


def _stream_sink_with_trace_id(
    sink: object,
    *,
    trace_id: str,
) -> object:
    if not callable(sink):
        return sink
    try:
        signature = inspect.signature(sink)
    except (TypeError, ValueError):
        return sink
    supports_trace_id = "trace_id" in signature.parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if not supports_trace_id:
        return sink

    def publish(event: object) -> None:
        sink(event, trace_id=trace_id)

    return publish


def _partial_reply_payload_from_stream_event(
    event: object,
    *,
    session_id: str,
    trace_id: str | None = None,
) -> tuple[str, object] | None:
    kind = getattr(event, "kind", None)
    trace_id = str(trace_id or getattr(event, "trace_id", "") or "")
    stream_id = str(getattr(event, "stream_id", "") or "")
    if not stream_id:
        return None
    if not trace_id:
        trace_id = stream_id
    if kind == "start":
        return (
            "emit_partial_reply_start",
            PartialReplyStartPayload(
                session_id=session_id,
                trace_id=trace_id,
                stream_id=stream_id,
            ),
        )
    if kind == "text_delta":
        return (
            "emit_partial_reply_delta",
            PartialReplyDeltaPayload(
                session_id=session_id,
                trace_id=trace_id,
                stream_id=stream_id,
                content_delta=str(getattr(event, "content_delta", "") or ""),
            ),
        )
    if kind == "final":
        return (
            "emit_partial_reply_complete",
            PartialReplyCompletePayload(
                session_id=session_id,
                trace_id=trace_id,
                stream_id=stream_id,
            ),
        )
    if kind == "failure":
        return (
            "emit_partial_reply_failed",
            PartialReplyFailedPayload(
                session_id=session_id,
                trace_id=trace_id,
                stream_id=stream_id,
                code=str(getattr(event, "reason", "") or "stream_failed"),
                message=getattr(event, "diagnostic", None),
            ),
        )
    return None


@dataclass(frozen=True, slots=True)
class RuntimeMediaExtractionResult:
    """Runtime media references extracted from persisted message content."""

    parts: tuple[RuntimeSourceMediaPart, ...] = ()
    diagnostics: tuple[RuntimeMediaDiagnostic, ...] = ()


def extract_runtime_media(
    content_json: str | None,
) -> RuntimeMediaExtractionResult:
    """Extract provider-neutral media references from stored message content."""

    if not content_json:
        return RuntimeMediaExtractionResult()
    try:
        content = json.loads(content_json)
    except json.JSONDecodeError:
        return RuntimeMediaExtractionResult()
    if not isinstance(content, dict):
        return RuntimeMediaExtractionResult()

    parts: list[RuntimeSourceMediaPart] = []
    diagnostics: list[RuntimeMediaDiagnostic] = []
    for segment in content.get("segments", ()):
        part = _runtime_media_part_from_segment(segment)
        if part is not None:
            parts.append(part)
            continue
        diagnostic = _runtime_media_diagnostic_from_segment(segment)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return RuntimeMediaExtractionResult(
        parts=tuple(parts),
        diagnostics=tuple(diagnostics),
    )


def _runtime_media_part_from_segment(
    segment: object,
) -> RuntimeSourceMediaPart | None:
    if not isinstance(segment, dict):
        return None
    seg_type = segment.get("type")
    if not isinstance(seg_type, str):
        return None
    kind = _runtime_media_kind(seg_type)
    if kind is None:
        return None

    url = _string_value(segment.get("url"))
    asset_id = _string_value(segment.get("asset_id"))
    file_ref = _string_value(
        segment.get("file") or segment.get("platform_file_id") or segment.get("file_id")
    )
    path_ref = _string_value(segment.get("path"))
    base64_data = _string_value(segment.get("base64"))
    if file_ref and file_ref.startswith("base64://") and not base64_data:
        base64_data = file_ref
        file_ref = None
    if not any((url, asset_id, file_ref, path_ref, base64_data)):
        return None

    return RuntimeSourceMediaPart(
        kind=kind,
        fallback_text=_media_fallback_text(kind=kind, segment=segment),
        url=url,
        asset_id=asset_id,
        file_ref=file_ref,
        path_ref=path_ref,
        base64_data=base64_data,
        file_name=_string_value(
            segment.get("file_name") or segment.get("name") or file_ref or path_ref
        ),
        mime_type=_string_value(segment.get("mime_type") or segment.get("mime")),
        size_bytes=_int_value(segment.get("size")),
        required=True,
        metadata={
            key: value
            for key in ("alt", "width", "height")
            if isinstance((value := segment.get(key)), (str, int, float, bool))
        },
    )


def _runtime_media_diagnostic_from_segment(
    segment: object,
) -> RuntimeMediaDiagnostic | None:
    if not isinstance(segment, dict):
        return None
    seg_type = segment.get("type")
    if not isinstance(seg_type, str):
        return None
    kind = _runtime_media_kind(seg_type)
    if kind is None:
        return None
    return RuntimeMediaDiagnostic(
        kind=kind,
        reason="missing_safe_reference",
        segment_type=seg_type,
    )


def _runtime_media_kind(seg_type: str) -> RuntimeSourceMediaKind | None:
    if seg_type in {"image", "img"}:
        return "image"
    if seg_type in {"audio", "voice", "record"}:
        return "audio"
    if seg_type in {"file", "video"}:
        return "file"
    return None


def _media_fallback_text(*, kind: str, segment: dict[str, object]) -> str:
    alt = _string_value(segment.get("alt"))
    if alt:
        return f"[{kind}: {alt}]"
    return f"[{kind}]"


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_value(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


__all__ = [
    "AIRuntimeIngressRequest",
    "DefaultAILiveRuntimeEntry",
    "RuntimeMediaExtractionResult",
    "extract_runtime_media",
]
