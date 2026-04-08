"""Tool execution recording and capability bridge service."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.tools.bridge import (
    AINoneBotCapabilityBridge,
    invoke_capability_with_policy,
)
from apeiria.app.ai.tools.capabilities import register_builtin_capabilities
from apeiria.app.ai.tools.models import (
    AICapabilityInvokeObservationOutput,
    AIMemoryQueryObservationInput,
    AIMemoryQueryObservationOutput,
    AINoneBotCapabilityRequest,
    AIRelationshipInspectObservationOutput,
    AIToolExecutionView,
    AIToolIntent,
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolPolicy,
    AIToolSpec,
    AIToolTurnCreateInput,
)
from apeiria.app.ai.tools.policy import evaluate_tool_policy
from apeiria.app.ai.tools.registry import AIToolRegistry
from apeiria.app.ai.tools.selection import plan_tool_intents_for_message
from apeiria.infra.db.models import AIToolExecution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIToolExecutionCreateInput:
    """Create payload for one persisted tool execution record."""

    conversation_id: str
    tool_name: str
    status: str
    input_payload: Any | None = None
    output_payload: Any | None = None


class AIToolService:
    """Tool registry, policy, and execution record service."""

    def __init__(self) -> None:
        self.registry = AIToolRegistry()
        self.capability_bridge = AINoneBotCapabilityBridge()
        self._register_builtin_tools()
        register_builtin_capabilities(self.capability_bridge)

    def _register_builtin_tools(self) -> None:
        """Register built-in AI-visible tool declarations."""

        for tool in (
            AIToolSpec(
                name="memory.query",
                description="inspect recalled long-term memory",
                read_only=True,
                concurrency_safe=True,
            ),
            AIToolSpec(
                name="relationship.inspect",
                description="inspect current affinity and mood projection",
                read_only=True,
                concurrency_safe=True,
            ),
            AIToolSpec(
                name="plugin.capability",
                description="invoke a whitelisted NoneBot capability bridge",
                read_only=False,
                concurrency_safe=False,
                risk_level="high",
                is_capability_bridge=True,
            ),
        ):
            self.registry.register(tool)

    def list_allowed_tools(self, policy: AIToolPolicy) -> list[AIToolSpec]:
        """List the tools allowed under one scene policy."""

        return [
            tool
            for tool in self.registry.list_tools()
            if evaluate_tool_policy(tool, policy).allowed
        ]

    async def observe_read_only_tools(
        self,
        session: AsyncSession,
        request: AIToolObservationRequest,
    ) -> list[AIToolObservationResult]:
        """Run low-risk read-only tool observations and persist execution logs."""

        allowed_tools = self.list_allowed_tools(request.policy)
        intents = plan_tool_intents_for_message(
            message_text=request.message_text,
            available_tools=allowed_tools,
        )
        return await self.execute_tool_intents(
            session,
            request=request,
            intents=intents,
        )

    async def execute_tool_intents(
        self,
        session: AsyncSession,
        *,
        request: AIToolObservationRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        """Execute pre-planned tool intents within the current scene policy."""

        observations: list[AIToolObservationResult] = []

        for intent in intents:
            if (
                intent.tool_name == "memory.query"
                and request.recalled_memory_contents
                and isinstance(intent.input_payload, AIMemoryQueryObservationInput)
            ):
                observations.append(
                    AIToolObservationResult(
                        tool_name=intent.tool_name,
                        summary=_format_memory_observation(
                            request.recalled_memory_contents,
                        ),
                        input_payload=intent.input_payload,
                        output_payload=AIMemoryQueryObservationOutput(
                            memory_ids=request.recalled_memory_ids,
                        ),
                    )
                )
                continue
            if (
                intent.tool_name == "relationship.inspect"
                and request.relationship_context
            ):
                observations.append(
                    AIToolObservationResult(
                        tool_name=intent.tool_name,
                        summary=(
                            "- [relationship.inspect] "
                            f"{request.relationship_context}"
                        ),
                        input_payload=intent.input_payload,
                        output_payload=AIRelationshipInspectObservationOutput(
                            relationship_context=request.relationship_context,
                        ),
                    )
                )
                continue
            if (
                intent.tool_name == "plugin.capability"
                and isinstance(intent.input_payload, AINoneBotCapabilityRequest)
            ):
                result = await self.invoke_capability(
                    request=intent.input_payload,
                    policy=request.policy,
                )
                observations.append(
                    AIToolObservationResult(
                        tool_name=intent.tool_name,
                        summary=_format_capability_observation(
                            intent.input_payload.capability_name,
                            result,
                        ),
                        input_payload=intent.input_payload,
                        output_payload=AICapabilityInvokeObservationOutput(
                            capability_name=intent.input_payload.capability_name,
                            result=result,
                        ),
                    )
                )

        for observation in observations:
            await self.record_execution(
                session,
                AIToolExecutionCreateInput(
                    conversation_id=request.conversation_id,
                    tool_name=observation.tool_name,
                    status="success",
                    input_payload=observation.input_payload,
                    output_payload=observation.output_payload,
                ),
        )
        return observations

    def build_tool_turns(
        self,
        observations: list[AIToolObservationResult],
    ) -> list[AIToolTurnCreateInput]:
        """Convert tool observations into context turns."""

        return [
            AIToolTurnCreateInput(
                sender_id="ai_tool_observation",
                content_text=observation.summary,
                raw_payload={
                    "source": "read_only_tool_observation",
                    "tool_name": observation.tool_name,
                    "input": _to_jsonable_payload(observation.input_payload),
                    "output": _to_jsonable_payload(observation.output_payload),
                },
            )
            for observation in observations
        ]

    async def invoke_capability(
        self,
        *,
        request: AINoneBotCapabilityRequest,
        policy: AIToolPolicy,
    ) -> Any:
        """Invoke one registered capability through the whitelist bridge."""

        return await invoke_capability_with_policy(
            registry=self.registry,
            bridge=self.capability_bridge,
            request=request,
            policy=policy,
        )

    async def record_execution(
        self,
        session: AsyncSession,
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecution:
        """Persist one tool execution record."""

        row = AIToolExecution(
            execution_id=f"tool_exec_{uuid4().hex}",
            conversation_id=create_input.conversation_id,
            tool_name=create_input.tool_name,
            status=create_input.status,
            input_json=(
                json.dumps(
                    _to_jsonable_payload(create_input.input_payload),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if create_input.input_payload is not None
                else None
            ),
            output_json=(
                json.dumps(
                    _to_jsonable_payload(create_input.output_payload),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if create_input.output_payload is not None
                else None
            ),
        )
        session.add(row)
        await session.flush()
        return row

    async def list_executions(
        self,
        session: AsyncSession,
        *,
        conversation_id: str,
    ) -> list[AIToolExecutionView]:
        """List persisted tool executions for one conversation."""

        result = await session.execute(
            select(AIToolExecution)
            .where(AIToolExecution.conversation_id == conversation_id)
            .order_by(AIToolExecution.created_at.asc(), AIToolExecution.id.asc())
        )
        rows = result.scalars().all()
        return [
            AIToolExecutionView(
                execution_id=row.execution_id,
                conversation_id=row.conversation_id,
                tool_name=row.tool_name,
                status=row.status,
                input_json=row.input_json,
                output_json=row.output_json,
                created_at=(
                    row.created_at.replace(tzinfo=timezone.utc)
                    if row.created_at.tzinfo is None
                    else row.created_at
                ),
            )
            for row in rows
        ]


ai_tool_service = AIToolService()


def _format_memory_observation(
    recalled_memory_contents: tuple[str, ...],
) -> str:
    memory_text = "; ".join(recalled_memory_contents[:3])
    return f"- [memory.query] Retrieved relevant memories: {memory_text}"


def _format_capability_observation(
    capability_name: str,
    result: Any,
) -> str:
    if isinstance(result, dict):
        summary = ", ".join(
            f"{key}={value}"
            for key, value in sorted(result.items())
        )
        return f"- [plugin.capability] {capability_name}: {summary}"
    return f"- [plugin.capability] {capability_name}: {result}"


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
