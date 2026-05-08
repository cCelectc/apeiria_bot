"""Runtime trace projection and compact persistence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from nonebot.log import logger

from apeiria.ai.diagnostics import sanitize_runtime_diagnostics
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.ai.turn_records import ModelAttempt, ToolAttempt
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.runtime.commit import RuntimeDeliveryOutcome
    from apeiria.app.ai.runtime.stages import (
        RuntimeTraceInput,
        RuntimeTraceOutcome,
    )
    from apeiria.app.ai.runtime.strategy import (
        RuntimeHardRuleAction,
        RuntimeHardRuleDecision,
    )


@dataclass(frozen=True, slots=True)
class TurnTrace:
    """Compact trace projection for one AI runtime turn."""

    trace_id: str
    session_id: str
    runtime_mode: str
    strategy_action: "RuntimeHardRuleAction"
    strategy_reason_codes: tuple[str, ...] = ()
    merged_message_count: int = 0
    merge_reason: str | None = None
    wait_reason: str | None = None
    defer_reason: str | None = None
    model_attempts: tuple["ModelAttempt", ...] = ()
    tool_attempts: tuple["ToolAttempt", ...] = ()
    final_response_source: str | None = None
    skip_reason: str | None = None
    delivery_status: str | None = None
    prompt_diagnostics: dict[str, object] | None = None
    multimodal: dict[str, object] | None = None
    capability_degradations: tuple[dict[str, object], ...] = ()

    def to_metadata(self) -> dict[str, object]:
        """Project the trace to compact metadata for diagnostics surfaces."""

        metadata: dict[str, object] = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "runtime_mode": self.runtime_mode,
            "strategy_action": self.strategy_action,
            "strategy_reason_codes": list(self.strategy_reason_codes),
            "merged_message_count": self.merged_message_count,
            "merge_reason": self.merge_reason,
            "wait_reason": self.wait_reason,
            "defer_reason": self.defer_reason,
            "model_attempt_count": len(self.model_attempts),
            "tool_attempt_count": len(self.tool_attempts),
            "tool_observation_count": len(self.tool_attempts),
            "final_response_source": self.final_response_source,
            "skip_reason": self.skip_reason,
            "delivery_status": self.delivery_status,
        }
        if self.prompt_diagnostics:
            metadata["prompt_diagnostics"] = self.prompt_diagnostics
        if self.multimodal:
            metadata["multimodal"] = self.multimodal
        if self.capability_degradations:
            metadata["capability_degradations"] = list(self.capability_degradations)
        return metadata


def project_turn_trace(  # noqa: PLR0913
    *,
    session_id: str,
    strategy_decision: "RuntimeHardRuleDecision",
    turn_result: "AgentTurnResult | None",
    trace_id: str | None = None,
    runtime_mode: str | None = None,
    delivery_result: "RuntimeDeliveryOutcome | None" = None,
) -> TurnTrace:
    """Project existing runtime attempt records into a compact turn trace."""

    resolved_trace_id = trace_id or (turn_result.trace_id if turn_result else "")
    resolved_runtime_mode = runtime_mode or (
        turn_result.runtime_mode if turn_result else "message"
    )
    skip_reason: str | None = None
    if turn_result is None:
        skip_reason = (
            strategy_decision.reason_codes[0]
            if strategy_decision.reason_codes
            else strategy_decision.action
        )
    elif turn_result.status == "skipped":
        skip_reason = turn_result.finish_reason

    return TurnTrace(
        trace_id=resolved_trace_id,
        session_id=session_id,
        runtime_mode=resolved_runtime_mode,
        strategy_action=strategy_decision.action,
        strategy_reason_codes=strategy_decision.reason_codes,
        merged_message_count=_int_evidence(strategy_decision, "merged_message_count"),
        merge_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "merge" and strategy_decision.reason_codes
            else None
        ),
        wait_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "wait" and strategy_decision.reason_codes
            else None
        ),
        defer_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "defer" and strategy_decision.reason_codes
            else None
        ),
        model_attempts=turn_result.model_attempts if turn_result else (),
        tool_attempts=turn_result.tool_attempts if turn_result else (),
        final_response_source=turn_result.response_source if turn_result else None,
        skip_reason=skip_reason,
        delivery_status=_delivery_status(delivery_result),
        prompt_diagnostics=_extract_prompt_diagnostics(turn_result),
        multimodal=_extract_multimodal_metadata(turn_result),
        capability_degradations=_extract_capability_degradations(turn_result),
    )


def _extract_prompt_diagnostics(
    turn_result: "AgentTurnResult | None",
) -> dict[str, object] | None:
    if turn_result is None:
        return None
    raw = turn_result.metadata.get("prompt_diagnostics")
    if not isinstance(raw, dict):
        return None
    diagnostics = dict(raw)
    multimodal = _safe_multimodal_metadata(raw.get("multimodal"))
    if multimodal:
        diagnostics["multimodal"] = multimodal
    elif "multimodal" in diagnostics:
        diagnostics.pop("multimodal")
    return diagnostics


def _extract_multimodal_metadata(
    turn_result: "AgentTurnResult | None",
) -> dict[str, object] | None:
    if turn_result is None:
        return None
    prompt_diagnostics = turn_result.metadata.get("prompt_diagnostics")
    if not isinstance(prompt_diagnostics, dict):
        return None
    return _safe_multimodal_metadata(prompt_diagnostics.get("multimodal"))


def _safe_multimodal_metadata(value: object) -> dict[str, object] | None:
    multimodal = value
    if not isinstance(multimodal, dict):
        return None

    metadata: dict[str, object] = {}
    projected = multimodal.get("projected")
    if isinstance(projected, bool):
        metadata["projected"] = projected
    counts = _safe_count_mapping(multimodal.get("media_counts"))
    if counts:
        metadata["media_counts"] = counts
    for key in ("required_media_count", "optional_media_count"):
        value = multimodal.get(key)
        if isinstance(value, int):
            metadata[key] = value
    return metadata or None


def _extract_capability_degradations(
    turn_result: "AgentTurnResult | None",
) -> tuple[dict[str, object], ...]:
    if turn_result is None:
        return ()
    raw = turn_result.metadata.get("capability_degradations")
    if not isinstance(raw, list):
        return ()

    degradations: list[dict[str, object]] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        reason = item.get("reason")
        if not isinstance(kind, str) or not isinstance(reason, str):
            continue
        degradation: dict[str, object] = {"kind": kind, "reason": reason}
        metadata = _safe_degradation_metadata(item.get("metadata"))
        if metadata:
            degradation["metadata"] = metadata
        degradations.append(degradation)
    return tuple(degradations)


def _safe_count_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        key: count
        for key, count in value.items()
        if isinstance(key, str) and isinstance(count, int)
    }


def _safe_degradation_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, object] = {}
    modalities = value.get("modalities")
    if isinstance(modalities, list):
        safe["modalities"] = [item for item in modalities if isinstance(item, str)][:10]
    elif isinstance(modalities, tuple):
        safe["modalities"] = tuple(
            item for item in modalities if isinstance(item, str)
        )[:10]
    return safe


def _int_evidence(
    strategy_decision: "RuntimeHardRuleDecision",
    key: str,
) -> int:
    value = strategy_decision.evidence.get(key)
    return value if isinstance(value, int) else 0


def _delivery_status(delivery_result: "RuntimeDeliveryOutcome | None") -> str:
    if delivery_result is None:
        return "not_required"
    return "delivered" if delivery_result.delivered else "failed"


class RuntimeTraceObserver(Protocol):
    """Optional observer for projected terminal runtime traces."""

    def __call__(self, outcome: "RuntimeTraceOutcome") -> None: ...


class RuntimeTraceStore(Protocol):
    """Durable compact trace storage collaborator."""

    def store_trace(
        self,
        trace: TurnTrace,
        *,
        terminal_status: str | None = None,
        commit_status: str | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> "TurnTraceRecord": ...


@dataclass(frozen=True, slots=True)
class RuntimeTraceProjectionStage:
    """Project and durably store compact terminal turn traces."""

    trace_observer: RuntimeTraceObserver | None = None
    trace_store: RuntimeTraceStore | None = None

    def project(
        self,
        *,
        trace_input: "RuntimeTraceInput",
    ) -> "RuntimeTraceOutcome":
        from apeiria.app.ai.runtime.stages import RuntimeTraceOutcome

        turn = trace_input.turn
        outcome = RuntimeTraceOutcome(
            stage="trace",
            trace=project_turn_trace(
                session_id=turn.identity.session_id,
                strategy_decision=trace_input.strategy_decision,
                turn_result=trace_input.turn_result,
                trace_id=trace_input.trace_id,
                runtime_mode=turn.runtime_mode,
                delivery_result=trace_input.delivery_result,
            ),
        )
        if self.trace_observer is not None:
            self.trace_observer(outcome)
        if self.trace_store is not None:
            self.trace_store.store_trace(
                outcome.trace,
                commit_status=trace_input.commit_status,
            )
        return outcome


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
        trace: TurnTrace,
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


def _terminal_status_for_trace(trace: TurnTrace) -> str:
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
    "RuntimeTraceObserver",
    "RuntimeTraceProjectionStage",
    "RuntimeTraceStore",
    "TurnTrace",
    "TurnTraceRecord",
    "TurnTraceRepository",
    "datetime_from_text",
    "datetime_to_text",
    "project_turn_trace",
    "row_to_record",
    "turn_trace_repository",
]
