"""Tool execution recording and capability bridge service."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.conversation.service import chat_session_service
from apeiria.app.ai.future_task import ai_future_task_service
from apeiria.app.ai.future_task.models import (
    AIFutureTaskCreateInput,
    AIFutureTaskDefinition,
    AIFutureTaskToolInput,
    AIFutureTaskToolItem,
    AIFutureTaskToolOutput,
)
from apeiria.app.ai.memory.service import (
    AIMemoryUpdateInput as AIMemoryUpdateWriteInput,
)
from apeiria.app.ai.memory.service import (
    ai_memory_service,
)
from apeiria.app.ai.model.models import AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
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
from apeiria.app.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.app.ai.tools.models import (
    AIMemoryQueryObservationInput,
    AIMemoryQueryObservationOutput,
    AIMemoryUpdateInput,
    AIMemoryUpdateObservationOutput,
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
from apeiria.app.ai.tools.selection import build_tool_planning_prompt
from apeiria.infra.db.models import AIToolExecution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ChatSessionIdentity


@dataclass(frozen=True)
class AIToolExecutionRequest:
    """Inputs needed to run tools for a single reply turn."""

    session_id: str
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

    session_id: str
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
                name="memory.update",
                description="revise one recalled memory when it is inaccurate",
                read_only=False,
                concurrency_safe=False,
                risk_level="low",
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
        intents = await self._plan_tool_intents_with_model(
            session=session,
            message_text=request.message_text,
            policy=request.policy,
            recalled_memory_ids=request.recalled_memory_ids,
            recalled_memory_contents=request.recalled_memory_contents,
            relationship_context=request.relationship_context,
        )
        return await self.execute_tool_intents(
            session,
            request=request,
            intents=intents,
        )

    async def preview_tool_intents(  # noqa: PLR0913
        self,
        *,
        session: "AsyncSession",
        message_text: str,
        policy: AIToolPolicy,
        recalled_memory_ids: tuple[str, ...] = (),
        recalled_memory_contents: tuple[str, ...] = (),
        relationship_context: str | None = None,
    ) -> list[AIToolIntentPreview]:
        intents = await self._plan_tool_intents_with_model(
            session=session,
            message_text=message_text,
            policy=policy,
            recalled_memory_ids=recalled_memory_ids,
            recalled_memory_contents=recalled_memory_contents,
            relationship_context=relationship_context,
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

    async def _plan_tool_intents_with_model(  # noqa: PLR0913
        self,
        *,
        session: "AsyncSession",
        message_text: str,
        policy: AIToolPolicy,
        recalled_memory_ids: tuple[str, ...],
        recalled_memory_contents: tuple[str, ...],
        relationship_context: str | None,
    ) -> list[AIToolIntent]:
        allowed_tools = self.list_allowed_tools(policy)
        if not allowed_tools:
            return []

        selected = await ai_model_facade.select_model(
            session,
            query=AIModelRouteQuery(task_class="tool_orchestration"),
        )
        if selected is None:
            return []

        response = await ai_model_facade.generate_text(
            selected,
            prompt=build_tool_planning_prompt(
                message_text=message_text,
                recalled_memory_ids=recalled_memory_ids,
                recalled_memory_contents=recalled_memory_contents,
                relationship_context=relationship_context,
            ),
            tools=build_function_tools(allowed_tools),
        )
        if response is None:
            return []

        return [
            intent
            for intent in build_intents_from_tool_calls(response.tool_calls)
            if intent.tool_name != "memory.update"
            or _memory_update_is_recalled(intent, recalled_memory_ids)
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
            if intent.tool_name == "future_task.manage" and isinstance(
                intent.input_payload, AIFutureTaskToolInput
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
                            request.recalled_memory_ids,
                            request.recalled_memory_contents,
                        ),
                        input_payload=intent.input_payload,
                        output_payload=AIMemoryQueryObservationOutput(
                            memory_ids=request.recalled_memory_ids,
                        ),
                    )
                )
                continue
            if intent.tool_name == "memory.update" and isinstance(
                intent.input_payload, AIMemoryUpdateInput
            ):
                observations.append(
                    await self._execute_memory_update_intent(
                        session=session,
                        request=request,
                        intent=intent,
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
                            f"- [relationship.inspect] {request.relationship_context}"
                        ),
                        input_payload=intent.input_payload,
                        output_payload=AIRelationshipInspectObservationOutput(
                            relationship_context=request.relationship_context,
                        ),
                    )
                )
                continue
            if intent.tool_name == "plugin.capability" and isinstance(
                intent.input_payload, AINoneBotCapabilityRequest
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
                    session_id=request.session_id,
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
                author_id="ai_tool_observation",
                text_content=observation.summary,
                meta={
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
            identity = await chat_session_service.get_session_identity(
                session,
                session_id=request.session_id,
            )
            if identity is None:
                return AIToolObservationResult(
                    tool_name="future_task.manage",
                    summary=(
                        "- [future_task.manage] failed: session identity is missing"
                    ),
                    input_payload=tool_input,
                    output_payload=AIFutureTaskToolOutput(
                        action=tool_input.action,
                        ok=False,
                        message="session identity is missing",
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
        identity: "ChatSessionIdentity",
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
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
        identity: "ChatSessionIdentity",
        tool_input: AIFutureTaskToolInput,
    ) -> AIFutureTaskToolOutput:
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
                session_id=identity.session_id,
                platform=identity.platform,
                scene_type=identity.scene_type,
                scene_id=identity.scene_id,
                user_id=identity.subject_id,
                title=tool_input.title or description[:32],
                description=description,
                trigger_at=trigger_at,
                source_message_id=request.source_message_id,
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
        if existing.session_id != request.session_id:
            return AIFutureTaskToolOutput(
                action="cancel",
                ok=False,
                message="task does not belong to the current session",
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
            session_id=request.session_id,
        )
        if not tasks:
            return AIFutureTaskToolOutput(
                action="list",
                ok=True,
                message="no future tasks in this session",
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

    async def _execute_memory_update_intent(
        self,
        *,
        session: "AsyncSession",
        request: AIToolObservationRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        tool_input = intent.input_payload
        assert isinstance(tool_input, AIMemoryUpdateInput)

        if tool_input.memory_id not in request.recalled_memory_ids:
            return AIToolObservationResult(
                tool_name="memory.update",
                summary=(
                    "- [memory.update] failed: memory_id is not available in the "
                    "current recalled memory set"
                ),
                input_payload=tool_input,
                output_payload={"ok": False, "message": "memory_id not recalled"},
                status="error",
            )

        existing = await ai_memory_service.get_memory(
            session,
            memory_id=tool_input.memory_id,
        )
        if existing is None:
            return AIToolObservationResult(
                tool_name="memory.update",
                summary=(
                    "- [memory.update] failed: "
                    f"memory {tool_input.memory_id} was not found"
                ),
                input_payload=tool_input,
                output_payload={"ok": False, "message": "memory not found"},
                status="error",
            )
        if (
            not existing.is_editable
            or existing.is_ignored
            or existing.memory_layer not in {"long_term", "knowledge", "operator"}
        ):
            return AIToolObservationResult(
                tool_name="memory.update",
                summary=(
                    "- [memory.update] failed: "
                    f"memory {tool_input.memory_id} is not editable in this layer"
                ),
                input_payload=tool_input,
                output_payload={"ok": False, "message": "memory not editable"},
                status="error",
            )

        row = await ai_memory_service.update_memory_content(
            session,
            memory_id=tool_input.memory_id,
            update_input=AIMemoryUpdateWriteInput(
                content=tool_input.updated_content,
                salience=tool_input.salience
                if tool_input.salience is not None
                else 0.8,
                confidence=tool_input.confidence
                if tool_input.confidence is not None
                else 0.85,
                source_message_id=request.source_message_id,
            ),
        )
        if row is None:
            return AIToolObservationResult(
                tool_name="memory.update",
                summary="- [memory.update] failed: update returned no row",
                input_payload=tool_input,
                output_payload={"ok": False, "message": "memory not found"},
                status="error",
            )
        if row.memory_layer == "knowledge":
            await ai_memory_service.upsert_memory_embedding(
                session,
                memory_id=row.memory_id,
                content=row.content,
            )
        return AIToolObservationResult(
            tool_name="memory.update",
            summary=(f"- [memory.update] Updated {row.memory_id}: {row.content}"),
            input_payload=tool_input,
            output_payload=AIMemoryUpdateObservationOutput(
                memory_id=row.memory_id,
                content=row.content,
                salience=row.salience,
                confidence=row.confidence,
            ),
        )

    async def record_execution(
        self,
        session: "AsyncSession",
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecution:
        row = AIToolExecution(
            execution_id=f"tool_exec_{uuid4().hex}",
            session_id=create_input.session_id,
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
        session_id: str,
    ) -> list[AIToolExecutionView]:
        result = await session.execute(
            select(AIToolExecution)
            .where(AIToolExecution.session_id == session_id)
            .order_by(AIToolExecution.created_at.asc(), AIToolExecution.id.asc())
        )
        rows = result.scalars().all()
        return [
            AIToolExecutionView(
                execution_id=row.execution_id,
                session_id=row.session_id,
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
    recalled_memory_ids: tuple[str, ...],
    recalled_memory_contents: tuple[str, ...],
) -> str:
    memory_text = "; ".join(
        f"{memory_id}={content}"
        for memory_id, content in zip(
            recalled_memory_ids[:3],
            recalled_memory_contents[:3],
            strict=False,
        )
    )
    return f"- [memory.query] Retrieved relevant memories: {memory_text}"


def _memory_update_is_recalled(
    intent: AIToolIntent,
    recalled_memory_ids: tuple[str, ...],
) -> bool:
    tool_input = intent.input_payload
    memory_id = getattr(tool_input, "memory_id", None)
    if not isinstance(memory_id, str):
        return True
    return memory_id in recalled_memory_ids


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
