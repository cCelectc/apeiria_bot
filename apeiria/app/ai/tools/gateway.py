"""Runtime-facing tool gateway for AI reply orchestration.

`ToolGateway` exposes the tool execution boundary that AI reply pipelines
speak to. Each tool invocation gets recorded as a `tool_call` `Effect`, so
tool usage is observable alongside model and delivery effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.app.ai.model.adapter import AIModelMessage
from apeiria.app.ai.model.gateway import model_gateway
from apeiria.app.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.app.ai.tools.models import AIToolObservationRequest, AIToolPolicy
from apeiria.app.ai.tools.policy import summarize_tool_policy
from apeiria.app.ai.tools.service import ai_tool_service
from apeiria.app.runtime.effect import (
    Effect,
    current_effect_queue,
    new_effect,
)
from apeiria.app.runtime.models import ToolResult
from apeiria.app.runtime.observer import current_request_id

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.model.adapter import (
        AIModelGenerateResponse,
        AIModelToolCall,
        AIModelToolDefinition,
    )
    from apeiria.app.ai.model.selection import AISelectedModel
    from apeiria.app.ai.tools.models import (
        AIToolObservationResult,
        AIToolTurnCreateInput,
    )

MAX_TOOL_ROUNDS = 3


@dataclass(frozen=True)
class ToolGatewayRequest:
    """Inputs needed to run tools for a single reply turn."""

    session_id: str
    source_message_id: str | None
    trace_id: str | None
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple["AIMemoryDefinition", ...]
    relationship_context: str | None
    current_time: datetime
    tool_mode: str = "allow"
    execution_timeout_seconds: float | None = None


@dataclass(frozen=True)
class ToolGatewayResult:
    """Aggregated tool runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]
    tool_results: tuple[ToolResult, ...] = ()
    available_tools: tuple["AIModelToolDefinition", ...] = ()
    final_response: "AIModelGenerateResponse | None" = None
    tool_messages: tuple[AIModelMessage, ...] = ()


class ToolGateway:
    """Runtime-level tool execution facade."""

    async def prepare(
        self,
        _session: "AsyncSession",
        request: ToolGatewayRequest,
    ) -> ToolGatewayResult:
        """Prepare tool definitions for a message turn (no execution yet)."""

        allowed_tools = ai_tool_service.list_allowed_tools(request.policy)
        if request.tool_mode == "avoid":
            allowed_tools = []
        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=(),
            turns=(),
            available_tools=build_function_tools(
                allowed_tools,
                current_time=request.current_time,
            ),
        )

    async def execute_tool_calls(
        self,
        session: "AsyncSession",
        request: ToolGatewayRequest,
        *,
        tool_calls: tuple["AIModelToolCall", ...],
        origin: str = "ai_runtime.tool_gateway",
    ) -> ToolGatewayResult:
        """Execute tool calls from a model response (single round)."""

        intents = build_intents_from_tool_calls(tool_calls)
        effects = [
            self._emit_effect(
                origin=origin,
                payload={
                    "tool_name": call.name,
                    "tool_call_id": call.tool_call_id,
                    "trace_id": request.trace_id,
                    "session_id": request.session_id,
                },
            )
            for call in tool_calls
        ]
        try:
            observations = await ai_tool_service.execute_tool_intents(
                session,
                request=self._build_observation_request(request),
                intents=intents,
            )
        except Exception as exc:
            for effect in effects:
                effect.mark_failed(str(exc))
            raise

        tool_results = _project_tool_results(tool_calls, observations)
        _finalize_effects(effects, tool_results)
        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(obs.summary for obs in observations),
            turns=tuple(ai_tool_service.build_tool_turns(observations)),
            tool_results=tool_results,
            available_tools=(),
        )

    async def run_tool_loop(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        request: ToolGatewayRequest,
        *,
        messages: list[AIModelMessage],
        tools: tuple["AIModelToolDefinition", ...],
        selected: "AISelectedModel",
        max_rounds: int = MAX_TOOL_ROUNDS,
        origin: str = "ai_runtime.tool_gateway",
    ) -> ToolGatewayResult:
        """Multi-round tool calling loop using the messages flow."""

        all_result_lines: list[str] = []
        all_turns: list[AIToolTurnCreateInput] = []
        all_tool_results: list[ToolResult] = []
        tool_message_history: list[AIModelMessage] = []
        final_response: AIModelGenerateResponse | None = None

        for round_idx in range(max_rounds):
            current_messages = tuple(messages) + tuple(tool_message_history)

            response = await model_gateway.generate_native(
                selected=selected,
                messages=current_messages,
                tools=tools,
                trace_id=request.trace_id,
                labels=("tool_loop",),
            )
            if response is None:
                break

            final_response = response
            if not response.tool_calls:
                break

            tool_message_history.append(
                AIModelMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            effects = [
                self._emit_effect(
                    origin=origin,
                    payload={
                        "tool_name": call.name,
                        "tool_call_id": call.tool_call_id,
                        "trace_id": request.trace_id,
                        "session_id": request.session_id,
                        "round": round_idx + 1,
                    },
                )
                for call in response.tool_calls
            ]
            intents = build_intents_from_tool_calls(response.tool_calls)
            try:
                observations = await ai_tool_service.execute_tool_intents(
                    session,
                    request=self._build_observation_request(request),
                    intents=intents,
                )
            except Exception as exc:
                for effect in effects:
                    effect.mark_failed(str(exc))
                raise

            tool_results = _project_tool_results(response.tool_calls, observations)
            _finalize_effects(effects, tool_results)
            all_tool_results.extend(tool_results)
            all_result_lines.extend(obs.summary for obs in observations)
            all_turns.extend(ai_tool_service.build_tool_turns(observations))

            obs_by_index = dict(enumerate(observations))
            for index, tool_call in enumerate(response.tool_calls):
                obs = obs_by_index.get(index)
                tool_message_history.append(
                    AIModelMessage(
                        role="tool",
                        content=(
                            obs.summary
                            if obs is not None
                            else f"- [{tool_call.name}] skipped: execution limit"
                        ),
                        tool_call_id=tool_call.tool_call_id,
                    )
                )

            logger.debug(
                "Tool loop round {} completed: {} tool calls, {} observations",
                round_idx + 1,
                len(response.tool_calls),
                len(observations),
            )

        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(all_result_lines),
            turns=tuple(all_turns),
            tool_results=tuple(all_tool_results),
            available_tools=(),
            final_response=final_response,
            tool_messages=tuple(tool_message_history),
        )

    @staticmethod
    def _build_observation_request(
        request: ToolGatewayRequest,
    ) -> AIToolObservationRequest:
        return AIToolObservationRequest(
            session_id=request.session_id,
            source_message_id=request.source_message_id,
            trace_id=request.trace_id,
            message_text=request.message_text,
            policy=request.policy,
            recalled_memory_ids=tuple(m.memory_id for m in request.recalled_memories),
            recalled_memory_contents=tuple(
                m.content for m in request.recalled_memories
            ),
            relationship_context=request.relationship_context,
            execution_timeout_seconds=request.execution_timeout_seconds,
        )

    @staticmethod
    def _emit_effect(*, origin: str, payload: dict[str, object]) -> Effect:
        effect = new_effect(
            kind="tool_call",
            origin=origin,
            request_id=current_request_id(),
            payload=payload,
        )
        queue = current_effect_queue()
        if queue is not None:
            queue.enqueue(effect)
        return effect


def _project_tool_results(
    tool_calls: tuple["AIModelToolCall", ...],
    observations: list["AIToolObservationResult"],
) -> tuple[ToolResult, ...]:
    obs_by_index = dict(enumerate(observations))
    results: list[ToolResult] = []
    for index, call in enumerate(tool_calls):
        obs = obs_by_index.get(index)
        if obs is None:
            results.append(
                ToolResult(
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                    summary=f"- [{call.name}] skipped: execution limit",
                    ok=False,
                    error="skipped_execution_limit",
                )
            )
            continue
        results.append(
            ToolResult(
                tool_call_id=call.tool_call_id,
                name=call.name,
                summary=obs.summary,
                ok=obs.status == "success",
                error=None if obs.status == "success" else obs.status,
                native_observation=obs,
            )
        )
    return tuple(results)


def _finalize_effects(
    effects: list[Effect],
    tool_results: tuple[ToolResult, ...],
) -> None:
    result_by_id = {result.tool_call_id: result for result in tool_results}
    for effect in effects:
        tool_call_id = effect.payload.get("tool_call_id")
        if isinstance(tool_call_id, str):
            matching = result_by_id.get(tool_call_id)
        else:
            matching = None
        if matching is None:
            effect.mark_dropped("no_result_returned")
            continue
        if matching.ok:
            effect.mark_flushed(
                {"tool_name": matching.name, "summary": matching.summary}
            )
        else:
            effect.mark_failed(matching.error or "tool_failed")


tool_gateway = ToolGateway()
