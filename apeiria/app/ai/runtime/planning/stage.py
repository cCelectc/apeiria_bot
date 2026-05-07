"""Default runtime turn planning stage implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from apeiria.app.ai.runtime.planning.turn import plan_runtime_turn

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.stages import RuntimePlanningInput, RuntimeTurnPlan


class RuntimePlanner(Protocol):
    """Prompt/model/tool planner collaborator for the default planning stage."""

    async def __call__(
        self,
        *,
        planning_input: "RuntimePlanningInput",
    ) -> "RuntimeTurnPlan | None": ...


@dataclass(frozen=True, slots=True)
class RuntimeTurnPlanningStage:
    """Plan prompt/model/tool materials for execution."""

    prepare_generation: RuntimePlanner = plan_runtime_turn

    async def plan(
        self,
        *,
        planning_input: "RuntimePlanningInput",
    ) -> "RuntimeTurnPlan | None":
        return await self.prepare_generation(planning_input=planning_input)


__all__ = ["RuntimePlanner", "RuntimeTurnPlanningStage"]
