"""Read models for managed AI session inventory and detail surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from apeiria.ai.persona.service import ai_persona_service
from apeiria.ai.token_usage import AIModelUsageRepository
from apeiria.app.ai.diagnostics.usage import AIModelUsageTotals
from apeiria.app.ai.runtime.trace import turn_trace_repository
from apeiria.app.ai.sessions.models import (
    AISessionDetail,
    AISessionDetailMessage,
    AISessionInventoryItem,
    AISessionManagementRecord,
    AISessionPersonaSummary,
    AISessionPromptPreviewEntry,
    AISessionTraceEntry,
)
from apeiria.app.ai.sessions.repository import AISessionManagementRepository
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from apeiria.ai.token_usage import AIModelUsageSummary
    from apeiria.conversation.models import ChatMessageDetailView


@dataclass(frozen=True, slots=True)
class AISessionManagementReader:
    """Compose read-only managed AI session views for operator surfaces."""

    repository: AISessionManagementRepository = field(
        default_factory=AISessionManagementRepository
    )
    usage_repository: AIModelUsageRepository = field(
        default_factory=AIModelUsageRepository
    )

    async def list_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list[AISessionInventoryItem]:
        records = await self.repository.list_sessions(limit=limit)
        items: list[AISessionInventoryItem] = []
        for record in records:
            messages = await chat_session_service.list_messages_for_session(
                session_id=record.session_id,
                limit=1000,
            )
            traces = turn_trace_repository.list_traces(
                limit=5,
                session_id=record.session_id,
            )
            items.append(
                AISessionInventoryItem(
                    session_id=record.session_id,
                    source_identity=record.source_identity,
                    source_labels=record.source_identity.source_labels,
                    ai_enabled=record.ai_enabled,
                    persona=await _persona_summary(record.persona_id),
                    last_observed_at=record.last_observed_at,
                    last_message_at=messages[-1].created_at if messages else None,
                    message_count=len(messages),
                    diagnostic_count=len(traces),
                )
            )
        return items

    async def get_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> AISessionDetail | None:
        record = await self.repository.get_session(session_id)
        if record is None:
            return None
        messages = await chat_session_service.list_messages_for_session(
            session_id=session_id,
            limit=message_limit,
        )
        traces = turn_trace_repository.list_traces(
            limit=10,
            session_id=session_id,
        )
        detail_messages = tuple(
            _detail_message(message, record=record) for message in messages
        )
        latest_trace = traces[0] if traces else None
        usage = _session_usage_totals(
            self.usage_repository.summarize_usage(
                group_by="session",
                session_id=session_id,
            )
        )
        return AISessionDetail(
            session_id=record.session_id,
            source_identity=record.source_identity,
            ai_enabled=record.ai_enabled,
            persona=await _persona_summary(record.persona_id),
            recent_messages=detail_messages,
            reset_boundary_at=record.context_reset_at,
            prompt_preview_entry=AISessionPromptPreviewEntry(
                session_id=record.session_id,
                available=bool(messages),
            ),
            trace_entries=tuple(
                AISessionTraceEntry(
                    trace_id=trace.trace_id,
                    terminal_status=trace.terminal_status,
                    skip_reason=trace.skip_reason,
                    created_at=trace.created_at,
                )
                for trace in traces
            ),
            model_summary={"last_model_name": _last_model_name(detail_messages)},
            strategy_summary={
                "last_action": latest_trace.strategy_action if latest_trace else None
            },
            tool_summary={
                "recent_tool_attempt_count": sum(
                    trace.tool_attempt_count for trace in traces
                )
            },
            diagnostics={
                "skipped_reply_reason": latest_trace.skip_reason
                if latest_trace is not None
                else None,
                "context_reset_at": (
                    record.context_reset_at.isoformat()
                    if record.context_reset_at is not None
                    else None
                ),
            },
            usage=usage,
        )


async def _persona_summary(persona_id: str | None) -> AISessionPersonaSummary | None:
    if persona_id is None:
        return None
    persona = await ai_persona_service.get_persona(
        persona_id=persona_id,
        include_disabled=True,
    )
    if persona is None:
        return None
    return AISessionPersonaSummary(
        persona_id=persona.persona_id,
        name=persona.name,
        enabled=persona.enabled,
    )


def _detail_message(
    message: "ChatMessageDetailView",
    *,
    record: AISessionManagementRecord,
) -> AISessionDetailMessage:
    before_reset = record.context_reset_at is not None and (
        message.created_at < record.context_reset_at
    )
    return AISessionDetailMessage(
        message_id=message.message_id,
        author_role=message.author_role,
        author_id=message.author_id,
        text_content=message.text_content,
        created_at=message.created_at,
        before_reset_boundary=before_reset,
        trace_id=message.trace_id,
        model_name=message.model_name,
    )


def _last_model_name(messages: tuple[AISessionDetailMessage, ...]) -> str | None:
    for message in reversed(messages):
        if message.model_name:
            return message.model_name
    return None


def _session_usage_totals(
    summaries: "list[AIModelUsageSummary]",
) -> AIModelUsageTotals:
    if not summaries:
        return AIModelUsageTotals()
    return AIModelUsageTotals(
        call_count=sum(getattr(item, "call_count", 0) for item in summaries),
        measured_call_count=sum(
            getattr(item, "measured_call_count", 0) for item in summaries
        ),
        missing_usage_count=sum(
            getattr(item, "missing_usage_count", 0) for item in summaries
        ),
        input_tokens=sum(getattr(item, "input_tokens", 0) for item in summaries),
        output_tokens=sum(getattr(item, "output_tokens", 0) for item in summaries),
        total_tokens=sum(getattr(item, "total_tokens", 0) for item in summaries),
        cached_input_tokens=sum(
            getattr(item, "cached_input_tokens", 0) for item in summaries
        ),
        reasoning_tokens=sum(
            getattr(item, "reasoning_tokens", 0) for item in summaries
        ),
        audio_input_tokens=sum(
            getattr(item, "audio_input_tokens", 0) for item in summaries
        ),
        audio_output_tokens=sum(
            getattr(item, "audio_output_tokens", 0) for item in summaries
        ),
    )


__all__ = ["AISessionManagementReader"]
