"""SQLite persistence for normalized AI tool observation records."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from apeiria.ai.diagnostics import sanitize_runtime_diagnostic
from apeiria.ai.tools.models import AIToolExecutionView
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from apeiria.ai.tools.contracts import AIToolObservationCreateInput


class AIToolExecutionRepository:
    """Own low-level SQL operations for tool observation history."""

    def record_observation(
        self,
        create_input: "AIToolObservationCreateInput",
    ) -> AIToolExecutionView:
        execution_id = f"tool_obs_{uuid4().hex}"
        created_at_text = _utcnow_text()
        input_json = _serialize_execution_payload(create_input.input_payload)
        output_json = _serialize_execution_payload(create_input.output_payload)

        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_tool_execution (
                    execution_id,
                    session_id,
                    tool_name,
                    status,
                    trace_id,
                    call_id,
                    reason,
                    input_json,
                    output_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    create_input.session_id,
                    create_input.tool_name,
                    create_input.status,
                    create_input.trace_id,
                    create_input.call_id,
                    create_input.reason,
                    input_json,
                    output_json,
                    created_at_text,
                ),
            )

        return AIToolExecutionView(
            execution_id=execution_id,
            session_id=create_input.session_id,
            tool_name=create_input.tool_name,
            status=create_input.status,
            trace_id=create_input.trace_id,
            call_id=create_input.call_id,
            reason=create_input.reason,
            input_json=input_json,
            output_json=output_json,
            created_at=_parse_datetime(created_at_text),
        )

    # Temporary alias while callers move to observation terminology.
    record_execution = record_observation

    def list_executions(
        self,
        *,
        session_id: str,
    ) -> list[AIToolExecutionView]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT
                    execution_id,
                    session_id,
                    tool_name,
                    status,
                    trace_id,
                    call_id,
                    reason,
                    input_json,
                    output_json,
                    created_at
                FROM ai_tool_execution
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            AIToolExecutionView(
                execution_id=str(row[0]),
                session_id=str(row[1]),
                tool_name=str(row[2]),
                status=row[3],
                trace_id=None if row[4] is None else str(row[4]),
                call_id=None if row[5] is None else str(row[5]),
                reason=None if row[6] is None else str(row[6]),
                input_json=None if row[7] is None else str(row[7]),
                output_json=None if row[8] is None else str(row[8]),
                created_at=_parse_datetime(str(row[9])),
            )
            for row in rows
        ]


def _serialize_execution_payload(payload: Any | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(
        sanitize_runtime_diagnostic(_to_jsonable_payload(payload)),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
