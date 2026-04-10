"""High-level skill runtime facade for AI reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.skills.models import AIToolObservationRequest, AIToolPolicy
from apeiria.app.ai.skills.policy import summarize_tool_policy
from apeiria.app.ai.skills.service import ai_skill_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.skills.models import AIToolTurnCreateInput


@dataclass(frozen=True)
class AIToolRuntimeRequest:
    """Inputs needed to run skills for a single reply turn."""

    conversation_id: str
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple["AIMemoryDefinition", ...]
    relationship_context: str | None


@dataclass(frozen=True)
class AIToolRuntimeResult:
    """Aggregated skill runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]


class AIToolRuntime:
    """Facade that hides skill planning/execution details from runtime."""

    async def run_for_message(
        self,
        session: "AsyncSession",
        request: AIToolRuntimeRequest,
    ) -> AIToolRuntimeResult:
        observations = await ai_skill_service.observe_read_only_tools(
            session,
            AIToolObservationRequest(
                conversation_id=request.conversation_id,
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
        )
        return AIToolRuntimeResult(
            policy_text=summarize_tool_policy(
                ai_skill_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(observation.summary for observation in observations),
            turns=tuple(ai_skill_service.build_tool_turns(observations)),
        )


ai_tool_runtime = AIToolRuntime()
