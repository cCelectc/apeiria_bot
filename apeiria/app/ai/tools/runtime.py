"""High-level tool runtime facade for AI reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.app.ai.model.adapter import AIModelMessage
from apeiria.app.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
)
from apeiria.app.ai.tools.models import AIToolObservationRequest, AIToolPolicy
from apeiria.app.ai.tools.policy import summarize_tool_policy
from apeiria.app.ai.tools.service import ai_tool_service

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
    from apeiria.app.ai.tools.models import AIToolTurnCreateInput

MAX_TOOL_ROUNDS = 3


@dataclass(frozen=True)
class AIToolRuntimeRequest:
    """Inputs needed to run tools for a single reply turn."""

    session_id: str
    source_message_id: str | None
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple["AIMemoryDefinition", ...]
    relationship_context: str | None
    current_time: datetime
    tool_mode: str = "allow"


@dataclass(frozen=True)
class AIToolRuntimeResult:
    """Aggregated tool runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]
    available_tools: tuple["AIModelToolDefinition", ...] = ()
    final_response: "AIModelGenerateResponse | None" = None
    tool_messages: tuple[AIModelMessage, ...] = ()


class AIToolRuntime:
    """Facade that hides tool planning/execution details from runtime."""

    async def run_for_message(
        self,
        _session: "AsyncSession",
        request: AIToolRuntimeRequest,
    ) -> AIToolRuntimeResult:
        """Prepare tool definitions for a message turn (no execution yet)."""

        allowed_tools = ai_tool_service.list_allowed_tools(request.policy)
        if request.tool_mode == "avoid":
            allowed_tools = []
        return AIToolRuntimeResult(
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
        request: AIToolRuntimeRequest,
        *,
        tool_calls: tuple[AIModelToolCall, ...],
    ) -> AIToolRuntimeResult:
        """Execute tool calls from a model response (single round)."""

        intents = build_intents_from_tool_calls(tool_calls)
        observations = await ai_tool_service.execute_tool_intents(
            session,
            request=AIToolObservationRequest(
                session_id=request.session_id,
                source_message_id=request.source_message_id,
                message_text=request.message_text,
                policy=request.policy,
                recalled_memory_ids=tuple(
                    memory.memory_id for memory in request.recalled_memories
                ),
                recalled_memory_contents=tuple(
                    memory.content for memory in request.recalled_memories
                ),
                relationship_context=request.relationship_context,
                execution_timeout_seconds=None,
            ),
            intents=intents,
        )
        return AIToolRuntimeResult(
            policy_text=summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(obs.summary for obs in observations),
            turns=tuple(ai_tool_service.build_tool_turns(observations)),
            available_tools=(),
        )

    async def run_tool_loop(  # noqa: PLR0913
        self,
        session: "AsyncSession",
        request: AIToolRuntimeRequest,
        *,
        messages: list[AIModelMessage],
        tools: tuple["AIModelToolDefinition", ...],
        selected: AISelectedModel,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> AIToolRuntimeResult:
        """Multi-round tool calling loop using proper messages flow.

        1. Call model with messages + tools
        2. If model returns tool_calls: execute, append tool_result messages
        3. Repeat until model returns text-only or max_rounds reached
        4. Return final response + accumulated tool messages
        """

        from apeiria.app.ai.model.service import ai_model_facade

        all_result_lines: list[str] = []
        all_turns: list["AIToolTurnCreateInput"] = []
        tool_message_history: list[AIModelMessage] = []
        final_response: AIModelGenerateResponse | None = None

        for round_idx in range(max_rounds):
            # Build current messages = original + accumulated tool interactions
            current_messages = tuple(messages) + tuple(tool_message_history)

            response = await ai_model_facade.generate_text(
                selected,
                messages=current_messages,
                tools=tools,
            )
            if response is None:
                break

            final_response = response

            if not response.tool_calls:
                break

            # Append assistant message with tool_calls
            tool_message_history.append(
                AIModelMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            # Execute tools and append results
            intents = build_intents_from_tool_calls(response.tool_calls)
            observations = await ai_tool_service.execute_tool_intents(
                session,
                request=AIToolObservationRequest(
                    session_id=request.session_id,
                    source_message_id=request.source_message_id,
                    message_text=request.message_text,
                    policy=request.policy,
                    recalled_memory_ids=tuple(
                        m.memory_id for m in request.recalled_memories
                    ),
                    recalled_memory_contents=tuple(
                        m.content for m in request.recalled_memories
                    ),
                    relationship_context=request.relationship_context,
                    execution_timeout_seconds=None,
                ),
                intents=intents,
            )

            all_result_lines.extend(obs.summary for obs in observations)
            all_turns.extend(ai_tool_service.build_tool_turns(observations))

            # Append tool result messages — every tool_call MUST get a
            # response, otherwise the API rejects the conversation.
            obs_by_index = dict(enumerate(observations))
            for i, tool_call in enumerate(response.tool_calls):
                obs = obs_by_index.get(i)
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

        return AIToolRuntimeResult(
            policy_text=summarize_tool_policy(
                ai_tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(all_result_lines),
            turns=tuple(all_turns),
            available_tools=(),
            final_response=final_response,
            tool_messages=tuple(tool_message_history),
        )


ai_tool_runtime = AIToolRuntime()
