"""Schema models for AI runtime trace inspection routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRecord


class AITurnTraceItem(BaseModel):
    trace_id: str
    session_id: str
    runtime_mode: str
    terminal_status: str
    strategy_action: str
    strategy_reason_codes: list[str]
    model_attempt_count: int
    tool_attempt_count: int
    final_response_source: str | None = None
    skip_reason: str | None = None
    delivery_status: str | None = None
    commit_status: str | None = None
    diagnostics: dict[str, Any]
    created_at: str


def to_ai_turn_trace_item(record: "TurnTraceRecord") -> AITurnTraceItem:
    return AITurnTraceItem(
        trace_id=record.trace_id,
        session_id=record.session_id,
        runtime_mode=record.runtime_mode,
        terminal_status=record.terminal_status,
        strategy_action=record.strategy_action,
        strategy_reason_codes=list(record.strategy_reason_codes),
        model_attempt_count=record.model_attempt_count,
        tool_attempt_count=record.tool_attempt_count,
        final_response_source=record.final_response_source,
        skip_reason=record.skip_reason,
        delivery_status=record.delivery_status,
        commit_status=record.commit_status,
        diagnostics=record.diagnostics,
        created_at=record.created_at.isoformat(),
    )


__all__ = ["AITurnTraceItem", "to_ai_turn_trace_item"]
