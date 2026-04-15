"""High-level tool runtime facade for AI reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    from apeiria.app.ai.model.adapter import AIModelToolCall, AIModelToolDefinition
    from apeiria.app.ai.tools.models import AIToolTurnCreateInput


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
    available_tools: tuple[AIModelToolDefinition, ...] = ()


class AIToolRuntime:
    """Facade that hides tool planning/execution details from runtime."""

    async def run_for_message(
        self,
        _session: "AsyncSession",
        request: AIToolRuntimeRequest,
    ) -> AIToolRuntimeResult:
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
            result_lines=tuple(observation.summary for observation in observations),
            turns=tuple(ai_tool_service.build_tool_turns(observations)),
            available_tools=(),
        )


ai_tool_runtime = AIToolRuntime()
