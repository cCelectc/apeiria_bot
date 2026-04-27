"""Tool execution recording and capability bridge service."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from typing import Any

from nonebot.log import logger

from apeiria.ai.tools.bridge import AINoneBotSkillBridge
from apeiria.ai.tools.capabilities import register_builtin_capabilities
from apeiria.ai.tools.contracts import AIToolExecutionCreateInput
from apeiria.ai.tools.debug import (
    AICapabilityDefinition,
    AICapabilityPreview,
    AIToolIntentPreview,
)
from apeiria.ai.tools.execution_repository import AIToolExecutionRepository
from apeiria.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.ai.tools.models import (
    AIToolExecutionContext,
    AIToolExecutionView,
    AIToolIntent,
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolPolicy,
    AIToolSpec,
    AIToolTurnCreateInput,
)
from apeiria.ai.tools.policy import evaluate_tool_policy
from apeiria.ai.tools.registry import AIToolRegistry
from apeiria.ai.tools.selection import build_tool_planning_prompt

MAX_CONSECUTIVE_FAILURES = 3


class AIToolService:
    """Runtime tool registry, policy, and execution service.

    Tool handlers are registered declaratively via ``@ai_tool`` decorators
    in the ``handlers/`` package.  This class provides unified dispatch,
    death-spiral detection, and execution recording.
    """

    def __init__(
        self,
        *,
        execution_repository: AIToolExecutionRepository | None = None,
    ) -> None:
        self.registry = AIToolRegistry()
        self.capability_bridge = AINoneBotSkillBridge()
        self._execution_repository = execution_repository or AIToolExecutionRepository()
        register_builtin_capabilities(self.capability_bridge)
        self._load_declarative_tools()

    def _load_declarative_tools(self) -> None:
        """Import handler modules and register all @ai_tool decorated specs."""

        count = self.registry.register_pending_tools()
        logger.debug("Registered {} declarative AI tools", count)

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

    # ------------------------------------------------------------------
    # Model-driven tool planning
    # ------------------------------------------------------------------

    async def observe_read_only_tools(
        self,
        request: AIToolObservationRequest,
    ) -> list[AIToolObservationResult]:
        intents = await self._plan_tool_intents_with_model(
            message_text=request.message_text,
            policy=request.policy,
            recalled_memory_ids=request.recalled_memory_ids,
            recalled_memory_contents=request.recalled_memory_contents,
            relationship_context=request.relationship_context,
        )
        return await self.execute_tool_intents(
            request=request,
            intents=intents,
        )

    async def preview_tool_intents(
        self,
        *,
        message_text: str,
        policy: AIToolPolicy,
        recalled_memory_ids: tuple[str, ...] = (),
        recalled_memory_contents: tuple[str, ...] = (),
        relationship_context: str | None = None,
    ) -> list[AIToolIntentPreview]:
        intents = await self._plan_tool_intents_with_model(
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

    async def _plan_tool_intents_with_model(
        self,
        *,
        message_text: str,
        policy: AIToolPolicy,
        recalled_memory_ids: tuple[str, ...],
        recalled_memory_contents: tuple[str, ...],
        relationship_context: str | None,
    ) -> list[AIToolIntent]:
        from apeiria.ai.model.gateway import model_gateway
        from apeiria.ai.model.models import AIModelRouteQuery

        allowed_tools = self.list_allowed_tools(policy)
        if not allowed_tools:
            return []

        selected = await model_gateway.select_model(
            query=AIModelRouteQuery(task_class="tool_orchestration"),
        )
        if selected is None:
            return []

        response = await model_gateway.generate_native(
            selected=selected,
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

    # ------------------------------------------------------------------
    # Unified tool execution with death-spiral detection
    # ------------------------------------------------------------------

    async def execute_tool_intents(
        self,
        *,
        request: AIToolObservationRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        """Execute tool intents via declarative entrypoints.

        Includes death-spiral detection: if ``MAX_CONSECUTIVE_FAILURES``
        consecutive tool calls fail, remaining intents are skipped.
        """

        observations: list[AIToolObservationResult] = []
        consecutive_failures = 0

        for intent in intents:
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    "Death spiral: {} consecutive tool failures, "
                    "skipping remaining {} intents",
                    consecutive_failures,
                    len(intents) - len(observations),
                )
                break

            observation = await self._execute_single_intent(
                request=request,
                intent=intent,
            )
            observations.append(observation)

            if observation.status == "success":
                consecutive_failures = 0
            else:
                consecutive_failures += 1

        for observation in observations:
            await self.record_execution(
                AIToolExecutionCreateInput(
                    session_id=request.session_id,
                    tool_name=observation.tool_name,
                    status=observation.status,
                    trace_id=request.trace_id,
                    input_payload=observation.input_payload,
                    output_payload=observation.output_payload,
                ),
            )

        return observations

    async def _execute_single_intent(
        self,
        *,
        request: AIToolObservationRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        """Execute one tool intent via its declarative entrypoint."""

        spec = self.registry.get(intent.tool_name)
        if spec is None or spec.entrypoint is None:
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=(
                    f"- [{intent.tool_name}] failed: tool not found or "
                    "has no entrypoint"
                ),
                input_payload=intent.input_payload,
                output_payload={"error": "tool not found"},
                status="error",
            )

        context = AIToolExecutionContext(
            session_id=request.session_id,
            source_message_id=request.source_message_id,
            trace_id=request.trace_id,
            message_text=request.message_text,
            policy=request.policy,
            recalled_memory_ids=request.recalled_memory_ids,
            recalled_memory_contents=request.recalled_memory_contents,
            relationship_context=request.relationship_context,
            execution_timeout_seconds=request.execution_timeout_seconds,
        )

        # Parse arguments from model output
        arguments = (
            intent.input_payload if isinstance(intent.input_payload, dict) else {}
        )

        try:
            execution = spec.entrypoint(**arguments, context=context)
            if request.execution_timeout_seconds is not None:
                result = await asyncio.wait_for(
                    execution,
                    timeout=request.execution_timeout_seconds,
                )
            else:
                result = await execution
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=result.summary,
                input_payload=intent.input_payload,
                output_payload=result.output_payload,
                status=result.status,
            )
        except TimeoutError:
            logger.warning(
                "Tool {} execution timed out trace_id={} timeout={}s",
                intent.tool_name,
                request.trace_id,
                request.execution_timeout_seconds,
            )
            timeout_summary = (
                f"- [{intent.tool_name}] timed out after "
                f"{request.execution_timeout_seconds:.1f}s"
                if request.execution_timeout_seconds is not None
                else f"- [{intent.tool_name}] timed out"
            )
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=timeout_summary,
                input_payload=intent.input_payload,
                output_payload={
                    "error": "timeout",
                    "timeout_seconds": request.execution_timeout_seconds,
                    "trace_id": request.trace_id,
                },
                status="timeout",
            )
        except TypeError as exc:
            logger.opt(exception=exc).debug(
                "Tool {} argument error trace_id={}: {}",
                intent.tool_name,
                request.trace_id,
                exc,
            )
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=f"- [{intent.tool_name}] failed: invalid arguments",
                input_payload=intent.input_payload,
                output_payload={
                    "error": f"invalid arguments: {exc}",
                    "trace_id": request.trace_id,
                },
                status="error",
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "Tool {} execution failed trace_id={}: {}",
                intent.tool_name,
                request.trace_id,
                exc,
            )
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=f"- [{intent.tool_name}] failed: {exc}",
                input_payload=intent.input_payload,
                output_payload={"error": str(exc), "trace_id": request.trace_id},
                status="error",
            )

    # ------------------------------------------------------------------
    # Turn building
    # ------------------------------------------------------------------

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
                    "trace_id": (
                        observation.output_payload.get("trace_id")
                        if isinstance(observation.output_payload, dict)
                        else None
                    ),
                    "tool_name": observation.tool_name,
                    "status": observation.status,
                    "input": _to_jsonable_payload(observation.input_payload),
                    "output": _to_jsonable_payload(observation.output_payload),
                },
            )
            for observation in observations
        ]

    # ------------------------------------------------------------------
    # Execution recording
    # ------------------------------------------------------------------

    async def record_execution(
        self,
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecutionView:
        return self._execution_repository.record_execution(create_input)

    async def list_executions(
        self,
        *,
        session_id: str,
    ) -> list[AIToolExecutionView]:
        return self._execution_repository.list_executions(session_id=session_id)

    # ------------------------------------------------------------------
    # Capability preview (admin/debug)
    # ------------------------------------------------------------------

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


def _memory_update_is_recalled(
    intent: AIToolIntent,
    recalled_memory_ids: tuple[str, ...],
) -> bool:
    if isinstance(intent.input_payload, dict):
        memory_id = intent.input_payload.get("memory_id")
    else:
        memory_id = getattr(intent.input_payload, "memory_id", None)
    if not isinstance(memory_id, str):
        return True
    return memory_id in recalled_memory_ids


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
