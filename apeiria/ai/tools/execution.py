"""Tool execution helpers and intent runtime."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.capabilities import AICapabilityBindingType
from apeiria.ai.tools.models import (
    AIToolExecutionContext,
    AIToolExecutionRequest,
    AIToolIntent,
    AIToolObservationResult,
)

if TYPE_CHECKING:
    from apeiria.ai.capabilities import AICapabilityBinding
    from apeiria.ai.tools.models import AIToolResult
    from apeiria.ai.tools.registry import AIToolRegistry

MAX_CONSECUTIVE_FAILURES = 3


class AIToolIntentExecutor:
    """Execute planned tool intents through registered entrypoints."""

    async def execute_tool_intents(
        self,
        *,
        registry: AIToolRegistry,
        bindings: "dict[str, AICapabilityBinding] | None" = None,
        request: AIToolExecutionRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        """Execute tool intents with consecutive failure detection."""

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
                registry=registry,
                bindings=bindings,
                request=request,
                intent=intent,
            )
            observations.append(observation)

            if observation.status == "success":
                consecutive_failures = 0
            else:
                consecutive_failures += 1

        return observations

    async def _execute_single_intent(
        self,
        *,
        registry: AIToolRegistry,
        bindings: "dict[str, AICapabilityBinding] | None",
        request: AIToolExecutionRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        binding = (
            bindings.get(intent.tool_name)
            if bindings is not None
            else registry.get_binding_for_contract(intent.tool_name)
        )
        if binding is None or binding.handler is None:
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=(
                    f"- [{intent.tool_name}] failed: capability not found or "
                    "has no binding"
                ),
                input_payload=intent.input_payload,
                output_payload={"error": "capability not found"},
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
        arguments = (
            intent.input_payload if isinstance(intent.input_payload, dict) else {}
        )

        try:
            if binding.binding_type is AICapabilityBindingType.HOST_ACTION:
                execution = binding.handler(arguments)
                if request.execution_timeout_seconds is not None:
                    result = await asyncio.wait_for(
                        _await_if_needed(execution),
                        timeout=request.execution_timeout_seconds,
                    )
                else:
                    result = await _await_if_needed(execution)
                result = _host_action_result(intent.tool_name, result)
            else:
                execution = binding.handler(**arguments, context=context)
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


def _host_action_result(
    action_name: str,
    result: Any,
) -> "AIToolResult":
    from apeiria.ai.tools.models import AIToolResult

    if isinstance(result, AIToolResult):
        return result
    return AIToolResult(
        summary=_format_host_action_observation(action_name, result),
        output_payload=result,
    )


def _format_host_action_observation(
    action_name: str,
    result: Any,
) -> str:
    if isinstance(result, dict):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
        return f"- [{action_name}] {summary}"
    return f"- [{action_name}] {result}"


async def _await_if_needed(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value
