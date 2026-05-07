"""Agent runner contract for one AI session turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from types import ModuleType

    from apeiria.app.ai.runtime.session.context import TurnContext
    from apeiria.app.ai.runtime.stages import RuntimeExecutionOutcome, RuntimeTurnPlan


def _execution_paths() -> "ModuleType":
    from apeiria.app.ai.runtime import execution

    return execution


@runtime_checkable
class AgentRunner(Protocol):
    """Protocol implemented by one-turn model/tool execution runners."""

    async def run_turn(
        self,
        context: "TurnContext",
        plan: "RuntimeTurnPlan",
    ) -> "RuntimeExecutionOutcome":
        """Run one turn from a frozen context and runtime-owned plan."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeAgentRunner:
    """Route one frozen turn to native direct or tool-capable execution."""

    async def run_turn(
        self,
        context: "TurnContext",
        plan: "RuntimeTurnPlan",
    ) -> "RuntimeExecutionOutcome":
        """Run the turn through the selected execution path."""

        execution = _execution_paths()
        if plan.has_executable_tools:
            return await execution.execute_tool_capable_runtime_turn(
                turn_context=context,
                plan=plan,
            )
        return await execution.execute_direct_runtime_turn(
            turn_context=context,
            plan=plan,
        )
