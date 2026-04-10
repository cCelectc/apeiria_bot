"""Skill execution recording and capability bridge service."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.skills.bridge import (
    AINoneBotSkillBridge,
    invoke_skill_with_policy,
)
from apeiria.app.ai.skills.capabilities import register_builtin_capabilities
from apeiria.app.ai.skills.debug import (
    AICapabilityDefinition,
    AICapabilityPreview,
)
from apeiria.app.ai.skills.execution import (
    build_capability_error_result,
    build_capability_success_result,
    build_capability_timeout_result,
)
from apeiria.app.ai.skills.models import (
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
from apeiria.app.ai.skills.policy import evaluate_tool_policy
from apeiria.app.ai.skills.registry import AIToolRegistry
from apeiria.app.ai.skills.selection import plan_tool_intents_for_message
from apeiria.infra.db.models import AIToolExecution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.skills.catalog import AISkillDefinition


@dataclass(frozen=True)
class AISkillRuntimeRequest:
    """Inputs needed to run skills for a single reply turn."""

    conversation_id: str
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple[object, ...]
    relationship_context: str | None


@dataclass(frozen=True)
class AISkillRuntimeResult:
    """Aggregated skill runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]


@dataclass(frozen=True)
class AIToolExecutionCreateInput:
    """Create payload for one persisted skill execution record."""

    conversation_id: str
    tool_name: str
    status: str
    input_payload: Any | None = None
    output_payload: Any | None = None


class AISkillService:
    """Product-facing skill registry, policy, and execution service."""

    DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0

    def __init__(self) -> None:
        self.registry = AIToolRegistry()
        self.capability_bridge = AINoneBotSkillBridge()
        self._register_builtin_tools()
        register_builtin_capabilities(self.capability_bridge)

    def _register_builtin_tools(self) -> None:
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

    def list_skills(self) -> list["AISkillDefinition"]:
        from apeiria.app.ai.skills.contracts import build_skill_definition

        return [
            build_skill_definition(tool)
            for tool in self.list_skill_specs()
        ]

    def list_skill_specs(
        self,
        policy: AIToolPolicy | None = None,
    ) -> list[AIToolSpec]:
        if policy is None:
            return self.registry.list_tools()
        return self.list_allowed_tools(policy)

    def list_allowed_tools(self, policy: AIToolPolicy) -> list[AIToolSpec]:
        return [
            tool
            for tool in self.registry.list_tools()
            if evaluate_tool_policy(tool, policy).allowed
        ]

    def list_capabilities(self) -> list[AICapabilityDefinition]:
        return [
            AICapabilityDefinition(
                capability_name=name,
                bound_tool_name="plugin.capability",
            )
            for name in self.capability_bridge.list_capabilities()
        ]

    async def observe_read_only_tools(
        self,
        session: "AsyncSession",
        request: AIToolObservationRequest,
    ) -> list[AIToolObservationResult]:
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
        session: "AsyncSession",
        *,
        request: AIToolObservationRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
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
                observation = await self._execute_capability_intent(
                    request=request,
                    intent=intent,
                )
                observations.append(observation)

        for observation in observations:
            await self.record_execution(
                session,
                AIToolExecutionCreateInput(
                    conversation_id=request.conversation_id,
                    tool_name=observation.tool_name,
                    status=observation.status,
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
                sender_id="ai_tool_observation",
                content_text=observation.summary,
                raw_payload={
                    "source": "read_only_tool_observation",
                    "tool_name": observation.tool_name,
                    "status": observation.status,
                    "input": _to_jsonable_payload(observation.input_payload),
                    "output": _to_jsonable_payload(observation.output_payload),
                },
            )
            for observation in observations
        ]

    async def _execute_capability_intent(
        self,
        *,
        request: AIToolObservationRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        capability_request = intent.input_payload
        assert isinstance(capability_request, AINoneBotCapabilityRequest)
        timeout_seconds = (
            request.execution_timeout_seconds or self.DEFAULT_TOOL_TIMEOUT_SECONDS
        )

        try:
            result = await asyncio.wait_for(
                self.invoke_capability(
                    request=capability_request,
                    policy=request.policy,
                ),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            return build_capability_timeout_result(
                capability_request,
                timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            return build_capability_error_result(
                capability_request,
                str(exc),
            )

        return build_capability_success_result(
            capability_request,
            result,
        )

    async def invoke_capability(
        self,
        *,
        request: AINoneBotCapabilityRequest,
        policy: AIToolPolicy,
    ) -> Any:
        return await invoke_skill_with_policy(
            registry=self.registry,
            bridge=self.capability_bridge,
            request=request,
            policy=policy,
        )

    async def record_execution(
        self,
        session: "AsyncSession",
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecution:
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
        session: "AsyncSession",
        *,
        conversation_id: str,
    ) -> list[AIToolExecutionView]:
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

    def preview_capability(
        self,
        *,
        capability_name: str,
        policy: AIToolPolicy,
    ) -> AICapabilityPreview:
        registered = self.capability_bridge.can_handle(capability_name)
        tool = self.registry.get(capability_name) or self.registry.get(
            "plugin.capability"
        )
        if not registered:
            return AICapabilityPreview(
                capability_name=capability_name,
                registered=False,
                allowed=False,
                reason="capability is not registered",
                allow_capability_bridge=policy.allow_capability_bridge,
                execution_enabled=policy.execution_enabled,
            )
        if tool is None:
            return AICapabilityPreview(
                capability_name=capability_name,
                registered=True,
                allowed=False,
                reason="capability tool binding is missing",
                allow_capability_bridge=policy.allow_capability_bridge,
                execution_enabled=policy.execution_enabled,
            )

        allowed_tools = self.list_allowed_tools(policy)
        allowed_tool_names = {item.name for item in allowed_tools}
        allowed = tool.name in allowed_tool_names
        reason = (
            "allowed by current skill policy"
            if allowed
            else "denied by current skill policy"
        )
        return AICapabilityPreview(
            capability_name=capability_name,
            registered=True,
            allowed=allowed,
            reason=reason,
            allow_capability_bridge=policy.allow_capability_bridge,
            execution_enabled=policy.execution_enabled,
        )


ai_skill_service = AISkillService()


def _format_memory_observation(
    recalled_memory_contents: tuple[str, ...],
) -> str:
    memory_text = "; ".join(recalled_memory_contents[:3])
    return f"- [memory.query] Retrieved relevant memories: {memory_text}"


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
