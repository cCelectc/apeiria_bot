"""Agent runner contract for one AI session turn."""

from __future__ import annotations

from collections.abc import Awaitable, Callable  # noqa: TC003
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from apeiria.app.ai.agent_turn import AgentTurnResult  # noqa: TC001

from .context import TurnContext  # noqa: TC001


@runtime_checkable
class AgentRunner(Protocol):
    """Protocol implemented by one-turn model/tool execution runners."""

    async def run_turn(self, context: TurnContext) -> AgentTurnResult:
        """Run one turn from a frozen context."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeAgentRunner:
    """Route one frozen turn to direct or tool-capable execution."""

    direct_executor: Callable[[TurnContext], Awaitable[AgentTurnResult]]
    tool_capable_executor: Callable[[TurnContext], Awaitable[AgentTurnResult]]

    async def run_turn(self, context: TurnContext) -> AgentTurnResult:
        """Run the turn through the selected execution path."""

        if context.tool_exposure_plan.has_executable_tools:
            return await self.tool_capable_executor(context)
        return await self.direct_executor(context)
