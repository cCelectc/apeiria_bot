"""Tool execution recording and capability bridge service."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.conversation.service import ai_conversation_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.future_task.models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskToolInput,
    AIFutureTaskToolItem,
    AIFutureTaskToolOutput,
)
from apeiria.app.ai.tools.bridge import (
    AINoneBotSkillBridge,
    invoke_skill_with_policy,
)
from apeiria.app.ai.tools.capabilities import register_builtin_capabilities
from apeiria.app.ai.tools.debug import (
    AICapabilityDefinition,
    AICapabilityPreview,
    AIToolIntentPreview,
)
from apeiria.app.ai.tools.execution import (
    build_capability_error_result,
    build_capability_success_result,
    build_capability_timeout_result,
)
from apeiria.app.ai.tools.models import (
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
class AIToolExecutionRequest:
    """Inputs needed to run tools for a single reply turn."""

    conversation_id: str
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple[object, ...]
    relationship_context: str | None


@dataclass(frozen=True)
class AIToolExecutionResult:
    """Aggregated tool runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]


@dataclass(frozen=True)
class AIToolExecutionCreateInput:
    """Create payload for one persisted tool execution record."""

    conversation_id: str
    tool_name: str
    status: str
    input_payload: Any | None = None
    output_payload: Any | None = None


class AIToolService:
    """Runtime tool registry, policy, and execution service."""

    DEFAULT_TOOL_TIMEOUT_SECONDS = 5.0

    def __init__(self) -> None:
        self.registry = AIToolRegistry()
        self.capability_bridge = AINoneBotSkillBridge()
        self._register_builtin_tools()
        register_builtin_capabilities(self.capability_bridge)

    def _register_builtin_tools(self) -> None:
        for tool in (
            AIToolSpec(
                name="future_task.manage",
                description="create, cancel, or inspect scheduled reminder tasks",
                read_only=False,
                concurrency_safe=False,
                risk_level="low",
            ),
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

    def list_tool_specs(
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

    def preview_tool_intents(
        self,
        *,
        message_text: str,
        policy: AIToolPolicy,
    ) -> list[AIToolIntentPreview]:
        allowed_tools = self.list_allowed_tools(policy)
        intents = plan_tool_intents_for_message(
            message_text=message_text,
            available_tools=allowed_tools,
        )
        return [
            AIToolIntentPreview(
                tool_name=intent.tool_name,
                kind=intent.kind,
                reason=intent.reason,
                input_payload=_to_jsonable_payload(intent.input_payload),
            )
            for intent in intents
        ]

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
                intent.tool_name == "future_task.manage"
                and isinstance(intent.input_payload, AIFutureTaskToolInput)
            ):
                observations.append(
                    await self._execute_future_task_intent(
                        session=session,
                        request=request,
                        intent=intent,
                    )
                )
                continue
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
                    "source": "tool_observation",
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

    async def _execute_future_task_intent(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        tool_input = intent.input_payload
        assert isinstance(tool_input, AIFutureTaskToolInput)

        try:
            identity = await ai_conversation_service.get_conversation_identity(
                session,
                conversation_id=request.conversation_id,
            )
            if identity is None:
                return AIToolObservationResult(
                    tool_name="future_task.manage",
                    summary=(
                        "- [future_task.manage] failed: "
                        "conversation identity is missing"
                    ),
                    input_payload=tool_input,
                    output_payload=AIFutureTaskToolOutput(
                        action=tool_input.action,
                        ok=False,
                        message="conversation identity is missing",
                    ),
                    status="error",
                )
            output = await self._run_future_task_action(
                session=session,
                request=request,
                identity=identity,
                tool_input=tool_input,
            )
        except Exception as exc:  # noqa: BLE001
            return AIToolObservationResult(
                tool_name="future_task.manage",
                summary=f"- [future_task.manage] failed: {exc}",
                input_payload=tool_input,
                output_payload=AIFutureTaskToolOutput(
                    action=tool_input.action,
                    ok=False,
                    message=str(exc),
                ),
                status="error",
            )

        return AIToolObservationResult(
            tool_name="future_task.manage",
            summary=_format_future_task_summary(output),
            input_payload=tool_input,
            output_payload=output,
            status="success" if output.ok else "error",
        )

    async def _run_future_task_action(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        identity: object,
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
        from apeiria.app.ai.conversation.models import AIConversationIdentity

        assert isinstance(identity, AIConversationIdentity)
        if tool_input.action == "create":
            return await self._create_future_task_action(
                session=session,
                request=request,
                identity=identity,
                tool_input=tool_input,
            )

        if tool_input.action == "cancel":
            return await self._cancel_future_task_action(
                session=session,
                request=request,
                tool_input=tool_input,
            )

        return await self._list_future_task_action(
            session=session,
            request=request,
            tool_input=tool_input,
        )

    async def _create_future_task_action(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        identity: object,
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
        from apeiria.app.ai.conversation.models import AIConversationIdentity

        assert isinstance(identity, AIConversationIdentity)
        description = tool_input.description
        trigger_at = tool_input.trigger_at
        if description is None:
            return AIFutureTaskToolOutput(
                action="create",
                ok=False,
                message="description is required for create",
            )
        if trigger_at is None:
            return AIFutureTaskToolOutput(
                action="create",
                ok=False,
                message="trigger_at must be an absolute ISO datetime with timezone",
            )
        result = await ai_future_task_service.create_task(
            session,
            AIFutureTaskCreateInput(
                conversation_id=identity.conversation_id,
                platform=identity.platform,
                scope_type=identity.scope_type,
                scope_id=identity.scope_id,
                user_id=identity.subject_user_id,
                title=tool_input.title or description[:32],
                description=description,
                trigger_at=trigger_at,
                source_turn_id=request.source_turn_id,
            ),
        )
        message = (
            ai_future_task_service.build_confirmation_message(result.task)
            if result.task.status == "pending"
            else ai_future_task_service.build_schedule_failed_message(result.task)
        )
        return AIFutureTaskToolOutput(
            action="create",
            ok=result.task.status == "pending",
            message=message,
            tasks=(self._to_tool_item(result.task),),
        )

    async def _cancel_future_task_action(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
        task_id = tool_input.task_id
        if task_id is None:
            return AIFutureTaskToolOutput(
                action="cancel",
                ok=False,
                message="task_id is required for cancel",
            )
        existing = await ai_future_task_service.get_task(session, task_id=task_id)
        if existing is None:
            return AIFutureTaskToolOutput(
                action="cancel",
                ok=False,
                message=f"task {task_id} was not found",
            )
        if existing.conversation_id != request.conversation_id:
            return AIFutureTaskToolOutput(
                action="cancel",
                ok=False,
                message="task does not belong to the current conversation",
            )
        cancelled = await ai_future_task_service.cancel_task(
            session,
            task_id=task_id,
        )
        if cancelled is None:
            return AIFutureTaskToolOutput(
                action="cancel",
                ok=False,
                message=f"task {task_id} was not found",
            )
        return AIFutureTaskToolOutput(
            action="cancel",
            ok=True,
            message=f"cancelled task {task_id}",
            tasks=(self._to_tool_item(cancelled),),
        )

    async def _list_future_task_action(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
        tasks = await ai_future_task_service.list_tasks(
            session,
            limit=max(1, min(tool_input.limit or 5, 10)),
            conversation_id=request.conversation_id,
        )
        if not tasks:
            return AIFutureTaskToolOutput(
                action="list",
                ok=True,
                message="no future tasks in this conversation",
            )
        return AIFutureTaskToolOutput(
            action="list",
            ok=True,
            message=f"listed {len(tasks)} future tasks",
            tasks=tuple(self._to_tool_item(task) for task in tasks),
        )

    @staticmethod
    def _to_tool_item(task: AIFutureTaskDefinition) -> AIFutureTaskToolItem:
        return AIFutureTaskToolItem(
            task_id=task.task_id,
            title=task.title,
            description=task.description,
            trigger_at=task.trigger_at,
            status=task.status,
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


ai_tool_service = AIToolService()


def _format_memory_observation(
    recalled_memory_contents: tuple[str, ...],
) -> str:
    memory_text = "; ".join(recalled_memory_contents[:3])
    return f"- [memory.query] Retrieved relevant memories: {memory_text}"


def _format_future_task_summary(output: AIFutureTaskToolOutput) -> str:
    if not output.tasks:
        return f"- [future_task.manage] {output.message}"
    task_text = "; ".join(
        (
            f"{task.task_id} ({task.status}) at "
            f"{task.trigger_at.isoformat()}: {task.description}"
        )
        for task in output.tasks
    )
    return f"- [future_task.manage] {output.message}. {task_text}"


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
