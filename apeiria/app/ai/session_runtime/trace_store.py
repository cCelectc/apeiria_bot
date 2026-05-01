"""Durable compact trace storage for AI runtime turns."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.diagnostics import sanitize_runtime_diagnostics
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.app.ai.session_runtime.trace import TurnTrace


@dataclass(frozen=True)
class TurnTraceRecord:
    """One durable compact terminal turn trace."""

    trace_id: str
    session_id: str
    runtime_mode: str
    terminal_status: str
    strategy_action: str
    strategy_reason_codes: tuple[str, ...]
    model_attempt_count: int
    tool_attempt_count: int
    final_response_source: str | None
    skip_reason: str | None
    delivery_status: str | None
    commit_status: str | None
    diagnostics: dict[str, object]
    created_at: datetime


class TurnTraceRepository:
    """Own SQL operations for compact AI turn traces."""

    def store_trace(
        self,
        trace: "TurnTrace",
        *,
        terminal_status: str | None = None,
        commit_status: str | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> TurnTraceRecord:
        metadata = sanitize_runtime_diagnostics(
            trace.to_metadata(),
            max_string_length=500,
        )
        if diagnostics:
            metadata.update(
                sanitize_runtime_diagnostics(
                    diagnostics,
                    max_string_length=500,
                )
            )
        record = TurnTraceRecord(
            trace_id=trace.trace_id,
            session_id=trace.session_id,
            runtime_mode=trace.runtime_mode,
            terminal_status=terminal_status or _terminal_status_for_trace(trace),
            strategy_action=trace.strategy_action,
            strategy_reason_codes=trace.strategy_reason_codes,
            model_attempt_count=len(trace.model_attempts),
            tool_attempt_count=len(trace.tool_attempts),
            final_response_source=trace.final_response_source,
            skip_reason=trace.skip_reason,
            delivery_status=trace.delivery_status,
            commit_status=commit_status,
            diagnostics=metadata,
            created_at=_utcnow(),
        )
        try:
            with database_runtime.connect_sync() as connection:
                connection.execute(
                    """
                    INSERT INTO ai_turn_trace (
                        trace_id,
                        session_id,
                        runtime_mode,
                        terminal_status,
                        strategy_action,
                        strategy_reason_codes_json,
                        model_attempt_count,
                        tool_attempt_count,
                        final_response_source,
                        skip_reason,
                        delivery_status,
                        commit_status,
                        diagnostics_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trace_id) DO UPDATE SET
                        session_id = excluded.session_id,
                        runtime_mode = excluded.runtime_mode,
                        terminal_status = excluded.terminal_status,
                        strategy_action = excluded.strategy_action,
                        strategy_reason_codes_json =
                            excluded.strategy_reason_codes_json,
                        model_attempt_count = excluded.model_attempt_count,
                        tool_attempt_count = excluded.tool_attempt_count,
                        final_response_source = excluded.final_response_source,
                        skip_reason = excluded.skip_reason,
                        delivery_status = excluded.delivery_status,
                        commit_status = excluded.commit_status,
                        diagnostics_json = excluded.diagnostics_json,
                        created_at = excluded.created_at
                    """,
                    _record_values(record),
                )
        except sqlite3.DatabaseError as exc:
            logger.opt(exception=exc).warning(
                "Failed to persist AI turn trace {}",
                trace.trace_id,
            )
        return record

    def get_trace(self, *, trace_id: str) -> TurnTraceRecord | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_TRACE_FIELDS + " WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()
        return None if row is None else row_to_record(row)

    def list_traces(  # noqa: PLR0913
        self,
        *,
        limit: int,
        trace_id: str | None = None,
        session_id: str | None = None,
        runtime_mode: str | None = None,
        terminal_status: str | None = None,
        commit_status: str | None = None,
    ) -> list[TurnTraceRecord]:
        clauses: list[str] = []
        params: list[object] = []
        for column_name, value in (
            ("trace_id", trace_id),
            ("session_id", session_id),
            ("runtime_mode", runtime_mode),
            ("terminal_status", terminal_status),
            ("commit_status", commit_status),
        ):
            if value is not None:
                clauses.append(f"{column_name} = ?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        bounded_limit = min(max(limit, 1), 100)
        params.append(bounded_limit)
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_TRACE_FIELDS
                + where
                + " ORDER BY created_at DESC, id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
        return [row_to_record(row) for row in rows]


_SELECT_TRACE_FIELDS = """
SELECT
    trace_id,
    session_id,
    runtime_mode,
    terminal_status,
    strategy_action,
    strategy_reason_codes_json,
    model_attempt_count,
    tool_attempt_count,
    final_response_source,
    skip_reason,
    delivery_status,
    commit_status,
    diagnostics_json,
    created_at
FROM ai_turn_trace
"""


def _record_values(record: TurnTraceRecord) -> tuple[object, ...]:
    return (
        record.trace_id,
        record.session_id,
        record.runtime_mode,
        record.terminal_status,
        record.strategy_action,
        json.dumps(list(record.strategy_reason_codes), ensure_ascii=False),
        record.model_attempt_count,
        record.tool_attempt_count,
        record.final_response_source,
        record.skip_reason,
        record.delivery_status,
        record.commit_status,
        json.dumps(record.diagnostics, ensure_ascii=False, sort_keys=True),
        datetime_to_text(record.created_at),
    )


def row_to_record(row: tuple[object, ...]) -> TurnTraceRecord:
    return TurnTraceRecord(
        trace_id=str(row[0]),
        session_id=str(row[1]),
        runtime_mode=str(row[2]),
        terminal_status=str(row[3]),
        strategy_action=str(row[4]),
        strategy_reason_codes=tuple(str(item) for item in _load_json_list(row[5])),
        model_attempt_count=int(str(row[6])),
        tool_attempt_count=int(str(row[7])),
        final_response_source=str(row[8]) if row[8] is not None else None,
        skip_reason=str(row[9]) if row[9] is not None else None,
        delivery_status=str(row[10]) if row[10] is not None else None,
        commit_status=str(row[11]) if row[11] is not None else None,
        diagnostics=_load_json_dict(row[12]),
        created_at=datetime_from_text(row[13]),
    )


def _terminal_status_for_trace(trace: "TurnTrace") -> str:
    if trace.skip_reason is not None:
        return "skipped"
    if trace.delivery_status == "failed":
        return "delivery_failed"
    if trace.model_attempts or trace.tool_attempts or trace.final_response_source:
        return "generated"
    return "terminal"


def _load_json_list(value: object) -> list[object]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _load_json_dict(value: object) -> dict[str, object]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


turn_trace_repository = TurnTraceRepository()


__all__ = [
    "TurnTraceRecord",
    "TurnTraceRepository",
    "turn_trace_repository",
]
