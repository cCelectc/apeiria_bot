"""AI-internal tool gateway for reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.model.adapter import AIModelMessage
from apeiria.ai.model.gateway import model_gateway
from apeiria.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.ai.tools.models import AIToolObservationRequest, AIToolPolicy
from apeiria.ai.tools.policy import summarize_tool_policy
from apeiria.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory.models import AIMemoryDefinition
    from apeiria.ai.model.adapter import (
        AIModelGenerateResponse,
        AIModelToolCall,
        AIModelToolDefinition,
    )
    from apeiria.ai.model.selection import AISelectedModel
    from apeiria.ai.tools.models import (
        AIToolObservationResult,
        AIToolTurnCreateInput,
    )

MAX_TOOL_ROUNDS = 3


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool call."""

    tool_call_id: str
    name: str
    summary: str
    ok: bool
    error: str | None = None
    native_observation: Any = None


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
    current_time: "datetime"
    tool_mode: str = "allow"
    execution_timeout_seconds: float | None = None


@dataclass(frozen=True)
class ToolGatewayResult:
    """Aggregated tool runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]
    tool_results: tuple[ToolResult, ...] = ()
    available_tools: tuple["AIModelToolDefinition", ...] = field(default_factory=tuple)
    final_response: "AIModelGenerateResponse | None" = None
    tool_messages: tuple[AIModelMessage, ...] = ()


class ToolGateway:
    """AI-internal tool execution facade."""

    async def prepare(
        self,
        request: ToolGatewayRequest,
    ) -> ToolGatewayResult:
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
        request: ToolGatewayRequest,
        *,
        tool_calls: tuple["AIModelToolCall", ...],
    ) -> ToolGatewayResult:
        intents = build_intents_from_tool_calls(tool_calls)
        observations = await ai_tool_service.execute_tool_intents(
            request=self._build_observation_request(request),
            intents=intents,
        )
        tool_results = _project_tool_results(tool_calls, observations)
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

    async def run_tool_loop(
        self,
        request: ToolGatewayRequest,
        *,
        messages: list[AIModelMessage],
        tools: tuple["AIModelToolDefinition", ...],
        selected: "AISelectedModel",
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> ToolGatewayResult:
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

            intents = build_intents_from_tool_calls(response.tool_calls)
            observations = await ai_tool_service.execute_tool_intents(
                request=self._build_observation_request(request),
                intents=intents,
            )
            tool_results = _project_tool_results(response.tool_calls, observations)
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


tool_gateway = ToolGateway()
