"""Default runtime turn execution stage implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.execution import execute_runtime_turn

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.session.context import TurnContext
    from apeiria.app.ai.runtime.stages import RuntimeExecutionOutcome, RuntimeTurnPlan


@dataclass(frozen=True, slots=True)
class RuntimeTurnExecutionStage:
    """Run the model/tool execution path for a planned turn."""

    async def execute(
        self,
        *,
        turn_context: "TurnContext",
        plan: "RuntimeTurnPlan",
    ) -> "RuntimeExecutionOutcome":
        return await execute_runtime_turn(
            turn_context=turn_context,
            plan=plan,
        )


__all__ = ["RuntimeTurnExecutionStage"]
