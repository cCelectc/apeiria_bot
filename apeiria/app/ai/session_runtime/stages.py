"""Provider-neutral runtime stage handoff contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from .context import RuntimeTurnSource, TurnContext  # noqa: TC001
from .strategy import RuntimeHardRuleDecision  # noqa: TC001
from .tools import ToolExposurePlan  # noqa: TC001
from .trace import TurnTrace  # noqa: TC001

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelMessage,
        AIModelTaskClass,
        AISelectedModel,
    )
    from apeiria.ai.prompting import PromptPacket
    from apeiria.ai.tools import ToolGatewayResult
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision


RuntimeStageName = Literal[
    "ingress",
    "policy",
    "context",
    "planning",
    "execution",
    "commit",
    "trace",
]


@dataclass(frozen=True, slots=True)
class RuntimePolicyOutcome:
    """Output of deterministic policy evaluation for one runtime turn."""

    stage: RuntimeStageName
    source: RuntimeTurnSource
    decision: RuntimeHardRuleDecision

    @property
    def should_continue(self) -> bool:
        """Return whether later context/planning/execution stages may run."""

        return self.decision.should_reply


@dataclass(frozen=True, slots=True)
class RuntimeContextBundle:
    """Read-oriented context materials gathered for one turn."""

    stage: RuntimeStageName
    inputs: "ReplyInputs"
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeTurnPlan:
    """Runtime-owned plan consumed by direct or tool-capable execution."""

    stage: RuntimeStageName
    selected: "AISelectedModel"
    fallback_models: tuple["AISelectedModel", ...]
    skill_runtime: "ToolGatewayResult"
    skill_activation: str | None
    pre_tool_task_class: "AIModelTaskClass"
    prompt_messages: tuple["AIModelMessage", ...]
    prompt_diagnostics: dict[str, object]
    tool_exposure_plan: ToolExposurePlan
    prompt_packet: "PromptPacket | None" = None
    post_tool_task_class: "AIModelTaskClass | None" = None

    @property
    def has_executable_tools(self) -> bool:
        """Return whether this plan selects executable tools for the turn."""

        return self.tool_exposure_plan.has_executable_tools


@dataclass(frozen=True, slots=True)
class RuntimeExecutionOutcome:
    """Output of direct or tool-capable model execution."""

    stage: RuntimeStageName
    response: Any | None
    skill_runtime: "ToolGatewayResult"
    post_tool_task_class: "AIModelTaskClass | None"
    delivery_result: "DeliveryOutcome | None"
    turn_result: "AgentTurnResult | None" = None


@dataclass(frozen=True, slots=True)
class RuntimeCommitResult:
    """Output of committing a generated turn."""

    stage: RuntimeStageName
    reply_text: str
    delivery_result: "DeliveryOutcome | None"
    trace: TurnTrace | None = None


@dataclass(frozen=True, slots=True)
class RuntimeTraceOutcome:
    """Trace projection for a terminal generated or non-generated turn."""

    stage: RuntimeStageName
    trace: TurnTrace
    context: TurnContext | None = None
    social_decision: "ReplyStrategyDecision | None" = None


__all__ = [
    "RuntimeCommitResult",
    "RuntimeContextBundle",
    "RuntimeExecutionOutcome",
    "RuntimePolicyOutcome",
    "RuntimeStageName",
    "RuntimeTraceOutcome",
    "RuntimeTurnPlan",
]
