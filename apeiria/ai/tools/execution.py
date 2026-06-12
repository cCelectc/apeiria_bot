"""Tool execution helpers and intent runtime."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.tools.models import (
    AIToolExecutionContext,
    AIToolExecutionRequest,
    AIToolIntent,
    AIToolObservationResult,
)
from apeiria.ai.tools.policy import evaluate_tool_policy

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolResult
    from apeiria.ai.tools.registry import AIToolRegistry

MAX_CONSECUTIVE_FAILURES = 3


class AIToolIntentExecutor:
    """Execute planned tool intents through registered tool executors."""

    async def execute_tool_intents(
        self,
        *,
        registry: "AIToolRegistry",
        request: AIToolExecutionRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        """Execute tool intents with exposure recheck and failure protection."""

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

    async def _execute_single_intent(  # noqa: PLR0911
        self,
        *,
        registry: "AIToolRegistry",
        request: AIToolExecutionRequest,
        intent: AIToolIntent,
    ) -> AIToolObservationResult:
        tool = registry.get(intent.tool_name)
        if tool is None:
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=f"- [{intent.tool_name}] failed: tool is not registered",
                input_payload=intent.input_payload,
                output_payload={"error": "tool is not registered"},
                status="error",
                reason="tool is not registered",
                call_id=intent.call_id,
            )

        decision = evaluate_tool_policy(tool, request.policy)
        if not decision.allowed:
            status = "not_ready" if not tool.readiness.ready else "denied"
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=f"- [{intent.tool_name}] not executed: {decision.reason}",
                input_payload=intent.input_payload,
                output_payload={"error": decision.reason},
                status=status,
                reason=decision.reason,
                call_id=intent.call_id,
            )

        if tool.executor is None:
            reason = "tool has no executor"
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=f"- [{intent.tool_name}] not executed: {reason}",
                input_payload=intent.input_payload,
                output_payload={"error": reason},
                status="not_ready",
                reason=reason,
                call_id=intent.call_id,
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
            actor_id=request.actor_id,
            chat_scope_type=request.chat_scope_type,
            chat_scope_id=request.chat_scope_id,
            reply_audience=request.reply_audience,
        )
        arguments = (
            intent.input_payload if isinstance(intent.input_payload, dict) else {}
        )
        arguments = {k: v for k, v in arguments.items() if k != "context"}

        try:
            execution = tool.executor(**arguments, context=context)
            if request.execution_timeout_seconds is not None:
                result = await asyncio.wait_for(
                    _await_if_needed(execution),
                    timeout=request.execution_timeout_seconds,
                )
            else:
                result = await _await_if_needed(execution)
            result = _tool_result(intent.tool_name, result)
            return AIToolObservationResult(
                tool_name=intent.tool_name,
                summary=result.summary,
                input_payload=intent.input_payload,
                output_payload=result.output_payload,
                status=result.status,
                call_id=intent.call_id,
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
                reason="timeout",
                call_id=intent.call_id,
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
                reason="invalid arguments",
                call_id=intent.call_id,
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
                reason=str(exc),
                call_id=intent.call_id,
            )


def _tool_result(
    tool_name: str,
    result: Any,
) -> "AIToolResult":
    from apeiria.ai.tools.models import AIToolResult

    if isinstance(result, AIToolResult):
        return result
    return AIToolResult(
        summary=_format_tool_observation(tool_name, result),
        output_payload=result,
    )


def _format_tool_observation(
    tool_name: str,
    result: Any,
) -> str:
    if isinstance(result, dict):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
        return f"- [{tool_name}] {summary}"
    return f"- [{tool_name}] {result}"


async def _await_if_needed(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


__all__ = ["MAX_CONSECUTIVE_FAILURES", "AIToolIntentExecutor"]
