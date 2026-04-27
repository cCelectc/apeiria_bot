"""Tool execution helpers and intent runtime."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.tools.models import (
    AICapabilityInvokeObservationOutput,
    AINoneBotCapabilityRequest,
    AIToolExecutionContext,
    AIToolIntent,
    AIToolObservationRequest,
    AIToolObservationResult,
)

if TYPE_CHECKING:
    from apeiria.ai.tools.registry import AIToolRegistry

MAX_CONSECUTIVE_FAILURES = 3


class AIToolIntentExecutor:
    """Execute planned tool intents through registered entrypoints."""

    async def execute_tool_intents(
        self,
        *,
        registry: AIToolRegistry,
        request: AIToolObservationRequest,
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
        request: AIToolObservationRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        spec = registry.get(intent.tool_name)
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


def build_capability_success_result(
    request: AINoneBotCapabilityRequest,
    result: Any,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_observation(request.capability_name, result),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result=result,
        ),
    )


def build_capability_error_result(
    request: AINoneBotCapabilityRequest,
    error_message: str,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_error(request.capability_name, error_message),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result={"error": error_message},
        ),
        status="error",
    )


def build_capability_timeout_result(
    request: AINoneBotCapabilityRequest,
    timeout_seconds: float,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_timeout(
            request.capability_name,
            timeout_seconds,
        ),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result={
                "error": "timeout",
                "timeout_seconds": timeout_seconds,
            },
        ),
        status="timeout",
    )


def _format_capability_observation(
    capability_name: str,
    result: Any,
) -> str:
    if isinstance(result, dict):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
        return f"- [plugin.capability] {capability_name}: {summary}"
    return f"- [plugin.capability] {capability_name}: {result}"


def _format_capability_error(
    capability_name: str,
    error_message: str,
) -> str:
    return f"- [plugin.capability] {capability_name} failed: {error_message}"


def _format_capability_timeout(
    capability_name: str,
    timeout_seconds: float,
) -> str:
    return (
        f"- [plugin.capability] {capability_name} timed out after "
        f"{timeout_seconds:.1f}s"
    )
