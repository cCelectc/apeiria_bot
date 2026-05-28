"""AI tool registry, execution, and observation service."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from apeiria.ai.tools.contracts import AIToolObservationCreateInput
from apeiria.ai.tools.execution import AIToolIntentExecutor
from apeiria.ai.tools.execution_repository import AIToolExecutionRepository
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


class AIToolService:
    """Runtime service for first-class AI tools."""

    def __init__(
        self,
        *,
        execution_repository: AIToolExecutionRepository | None = None,
        intent_executor: AIToolIntentExecutor | None = None,
    ) -> None:
        self.registry = AIToolRegistry()
        self._execution_repository = execution_repository or AIToolExecutionRepository()
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
        return self._execution_repository.record_observation(create_input)

    async def list_executions(
        self,
        *,
        session_id: str,
    ) -> list[AIToolExecutionView]:
        return self._execution_repository.list_executions(session_id=session_id)

    async def list_recent_executions(
        self,
        *,
        limit: int,
    ) -> list[AIToolExecutionView]:
        return self._execution_repository.list_recent_executions(limit=limit)


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload


__all__ = [
    "AIToolObservationCreateInput",
    "AIToolService",
]
