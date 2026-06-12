"""AI tool registry, execution, and observation service."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from apeiria.ai.diagnostics import sanitize_runtime_diagnostic
from apeiria.ai.tools.contracts import AIToolObservationCreateInput
from apeiria.ai.tools.execution import AIToolIntentExecutor
from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolExecutionRequest,
    AIToolExecutionView,
    AIToolIntent,
    AIToolObservationResult,
    AIToolPolicy,
    AIToolTurnCreateInput,
)
from apeiria.ai.tools.policy import evaluate_tool_policy
from apeiria.ai.tools.registry import AIToolRegistry, AIToolRegistrySnapshot
from apeiria.ai.trace_broker import TraceRecord, trace_broker


class AIToolService:
    """Runtime service for first-class AI tools."""

    def __init__(
        self,
        *,
        intent_executor: AIToolIntentExecutor | None = None,
    ) -> None:
        self.registry = AIToolRegistry()
        self._intent_executor = intent_executor or AIToolIntentExecutor()

    def list_tool_specs(
        self,
        policy: AIToolPolicy | None = None,
    ) -> list[AIToolDefinition]:
        if policy is None:
            return list(self.registry.snapshot().tools)
        return self.list_allowed_tools(policy)

    def list_allowed_tools(self, policy: AIToolPolicy) -> list[AIToolDefinition]:
        return [
            tool
            for tool in self.registry.snapshot().tools
            if evaluate_tool_policy(tool, policy).allowed
        ]

    def snapshot(self) -> AIToolRegistrySnapshot:
        return self.registry.snapshot()

    async def execute_tool_intents(
        self,
        *,
        request: AIToolExecutionRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        observations = await self._intent_executor.execute_tool_intents(
            registry=self.registry,
            request=request,
            intents=intents,
        )

        for observation in observations:
            await self.record_observation(
                AIToolObservationCreateInput(
                    session_id=request.session_id,
                    tool_name=observation.tool_name,
                    status=observation.status,
                    trace_id=request.trace_id,
                    call_id=observation.call_id,
                    reason=observation.reason,
                    input_payload=observation.input_payload,
                    output_payload=observation.output_payload,
                ),
            )

        return observations

    def build_tool_turns(
        self,
        observations: list[AIToolObservationResult],
    ) -> list[AIToolTurnCreateInput]:
        return [
            AIToolTurnCreateInput(
                author_id="ai_tool_observation",
                text_content=observation.summary,
                meta={
                    "source": "tool_observation",
                    "tool_name": observation.tool_name,
                    "status": observation.status,
                    "reason": observation.reason,
                    "call_id": observation.call_id,
                    "input": _to_jsonable_payload(observation.input_payload),
                    "output": _to_jsonable_payload(observation.output_payload),
                },
            )
            for observation in observations
        ]

    async def record_observation(
        self,
        create_input: AIToolObservationCreateInput,
    ) -> AIToolExecutionView:
        execution_id = f"tool_obs_{uuid4().hex}"
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        input_json = _serialize_execution_payload(create_input.input_payload)
        output_json = _serialize_execution_payload(create_input.output_payload)

        trace_broker.record(
            TraceRecord(
                trace_id=create_input.trace_id or execution_id,
                record_type="tool_execution",
                session_id=create_input.session_id,
                data={
                    "execution_id": execution_id,
                    "session_id": create_input.session_id,
                    "tool_name": create_input.tool_name,
                    "status": create_input.status,
                    "trace_id": create_input.trace_id,
                    "call_id": create_input.call_id,
                    "reason": create_input.reason,
                    "input_json": input_json,
                    "output_json": output_json,
                    "created_at": created_at.isoformat(timespec="seconds"),
                },
            )
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
            created_at=created_at,
        )

    async def list_executions(
        self,
        *,
        session_id: str,
    ) -> list[AIToolExecutionView]:
        items = trace_broker.snapshot(record_type="tool_execution", limit=1000)
        return [
            _data_to_execution_view(item.data)
            for item in items
            if item.session_id == session_id
        ]

    async def list_recent_executions(
        self,
        *,
        limit: int,
    ) -> list[AIToolExecutionView]:
        items = trace_broker.snapshot(record_type="tool_execution", limit=limit)
        return [_data_to_execution_view(item.data) for item in reversed(items)]


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload


def _serialize_execution_payload(payload: Any | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(
        sanitize_runtime_diagnostic(_to_jsonable_payload(payload)),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _data_to_execution_view(data: dict) -> AIToolExecutionView:
    return AIToolExecutionView(
        execution_id=str(data.get("execution_id", "")),
        session_id=str(data.get("session_id", "")),
        tool_name=str(data.get("tool_name", "")),
        status=data.get("status", "unknown"),
        trace_id=data.get("trace_id"),
        call_id=data.get("call_id"),
        reason=data.get("reason"),
        input_json=data.get("input_json"),
        output_json=data.get("output_json"),
        created_at=datetime.fromisoformat(data["created_at"])
        if data.get("created_at")
        else datetime.now(timezone.utc),
    )


__all__ = [
    "AIToolObservationCreateInput",
    "AIToolService",
]
