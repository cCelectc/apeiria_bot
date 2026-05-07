"""Provider-neutral runtime stage handoff contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from .commit import RuntimeDeliveryOutcome  # noqa: TC001
from .planning.tool_exposure import ToolExposurePlan  # noqa: TC001
from .session.context import (  # noqa: TC001
    RuntimeContextMaterials,
    RuntimeTurnInput,
    RuntimeTurnSource,
    TurnContext,
)
from .session.runtime import InMemoryAISessionRuntime  # noqa: TC001
from .strategy import RuntimeHardRuleDecision  # noqa: TC001
from .trace import TurnTrace  # noqa: TC001

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import (
        AIModelMessage,
        AIModelTaskClass,
        AISelectedModel,
    )
    from apeiria.ai.prompting import PromptPacket
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
    from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
    from apeiria.app.ai.runtime.planning.prompts import RuntimePromptComposeInput

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
    context: RuntimeContextMaterials
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def inputs(self) -> RuntimeContextMaterials:
        """Compatibility alias while callers move to runtime context materials."""

        return self.context


@dataclass(frozen=True, slots=True)
class RuntimeIngressInput:
    """Typed source input shared by pre-planning ingress stages."""

    stage: RuntimeStageName
    turn: RuntimeTurnInput
    current_time: "datetime"
    wake_context: "WakeContext"
    session_runtime: "InMemoryAISessionRuntime | None" = None


@dataclass(frozen=True, slots=True)
class RuntimePlanningInput:
    """Typed planning-stage input normalized by the turn engine."""

    stage: RuntimeStageName
    trace_id: str
    turn: RuntimeTurnInput
    context: RuntimeContextMaterials
    social_decision: "ReplyStrategyDecision"
    current_time: "datetime"


@dataclass(frozen=True, slots=True)
class RuntimeSocialDecisionInput:
    """Typed input for social reply policy judgment."""

    stage: RuntimeStageName
    trace_id: str
    turn: RuntimeTurnInput
    wake_context: "WakeContext"
    context: RuntimeContextBundle
    current_time: "datetime"


@dataclass(frozen=True, slots=True)
class RuntimeTurnPlan:
    """Runtime-owned plan consumed by direct or tool-capable execution."""

    stage: RuntimeStageName
    selected: "AISelectedModel"
    fallback_models: tuple["AISelectedModel", ...]
    skill_runtime: "RuntimeToolLoopResult"
    skill_activation: str | None
    pre_tool_task_class: "AIModelTaskClass"
    prompt_messages: tuple["AIModelMessage", ...]
    prompt_diagnostics: dict[str, object]
    tool_exposure_plan: ToolExposurePlan
    reply_compose_input: "RuntimePromptComposeInput | None" = None
    prompt_packet: "PromptPacket | None" = None
    tool_mode: str = "allow"
    tool_execution_timeout_seconds: float | None = None
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
    skill_runtime: "RuntimeToolLoopResult"
    post_tool_task_class: "AIModelTaskClass | None"
    delivery_result: "RuntimeDeliveryOutcome | None"
    turn_result: "AgentTurnResult | None" = None


@dataclass(frozen=True, slots=True)
class RuntimeCommitInput:
    """Typed input for committing one generated turn."""

    stage: RuntimeStageName
    trace_id: str
    turn: RuntimeTurnInput
    context: RuntimeContextMaterials
    social_decision: "ReplyStrategyDecision"
    plan: RuntimeTurnPlan
    generation: RuntimeExecutionOutcome
    hard_decision: RuntimeHardRuleDecision
    current_time: "datetime"
    session_runtime: "InMemoryAISessionRuntime | None" = None


@dataclass(frozen=True, slots=True)
class RuntimeCommitResult:
    """Output of committing a generated turn."""

    stage: RuntimeStageName
    reply_text: str
    delivery_result: "RuntimeDeliveryOutcome | None"
    trace: TurnTrace | None = None
    commit_status: str = "committed"
    substeps: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeTraceOutcome:
    """Trace projection for a terminal generated or non-generated turn."""

    stage: RuntimeStageName
    trace: TurnTrace
    context: TurnContext | None = None
    social_decision: "ReplyStrategyDecision | None" = None


@dataclass(frozen=True, slots=True)
class RuntimeTraceInput:
    """Typed input for terminal turn trace projection."""

    stage: RuntimeStageName
    trace_id: str
    turn: RuntimeTurnInput
    strategy_decision: RuntimeHardRuleDecision
    turn_result: "AgentTurnResult | None"
    delivery_result: "RuntimeDeliveryOutcome | None" = None
    commit_status: str | None = None


@runtime_checkable
class RuntimePolicyStage(Protocol):
    """Deterministic and social policy boundary for one turn."""

    def evaluate(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimePolicyOutcome: ...

    async def decide_reply(
        self,
        *,
        social_input: RuntimeSocialDecisionInput,
    ) -> "ReplyStrategyDecision": ...


@runtime_checkable
class RuntimeObservationStage(Protocol):
    """Live observation side-effect boundary before read context assembly."""

    async def apply(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> None: ...


@runtime_checkable
class RuntimeContextStage(Protocol):
    """Read-oriented context assembly boundary for one turn."""

    async def assemble(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimeContextBundle: ...


@runtime_checkable
class RuntimePlanningStage(Protocol):
    """Prompt/model/tool planning boundary for one turn."""

    async def plan(
        self,
        *,
        planning_input: RuntimePlanningInput,
    ) -> RuntimeTurnPlan | None: ...


@runtime_checkable
class RuntimeExecutionStage(Protocol):
    """Model/tool execution boundary for one turn."""

    async def execute(
        self,
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome: ...


@runtime_checkable
class RuntimeCommitStage(Protocol):
    """Post-execution side-effect boundary for one generated turn."""

    async def commit(
        self,
        *,
        commit_input: RuntimeCommitInput,
    ) -> RuntimeCommitResult: ...


@runtime_checkable
class RuntimeTraceStage(Protocol):
    """Terminal compact trace projection and persistence boundary."""

    def project(
        self,
        *,
        trace_input: RuntimeTraceInput,
    ) -> RuntimeTraceOutcome: ...


__all__ = [
    "RuntimeCommitInput",
    "RuntimeCommitResult",
    "RuntimeCommitStage",
    "RuntimeContextBundle",
    "RuntimeContextStage",
    "RuntimeExecutionOutcome",
    "RuntimeExecutionStage",
    "RuntimeIngressInput",
    "RuntimeObservationStage",
    "RuntimePlanningInput",
    "RuntimePlanningStage",
    "RuntimePolicyOutcome",
    "RuntimePolicyStage",
    "RuntimeSocialDecisionInput",
    "RuntimeStageName",
    "RuntimeTraceInput",
    "RuntimeTraceOutcome",
    "RuntimeTraceStage",
    "RuntimeTurnPlan",
]
