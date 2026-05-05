"""Provider-neutral runtime stage handoff contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from .context import RuntimeTurnSource, TurnContext  # noqa: TC001
from .strategy import RuntimeHardRuleDecision  # noqa: TC001
from .tools import ToolExposurePlan  # noqa: TC001
from .trace import TurnTrace  # noqa: TC001

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import (
        AIModelMessage,
        AIModelTaskClass,
        AISelectedModel,
    )
    from apeiria.ai.prompting import PromptPacket
    from apeiria.ai.tools import ToolGatewayResult
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.composer import AIRuntimeComposeInput
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.pipeline.input_steps import ReplyInputs
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext


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
class RuntimePlanningInput:
    """Typed planning-stage input normalized by the turn engine."""

    stage: RuntimeStageName
    trace_id: str
    request: "AIRuntimeReplyRequest"
    inputs: "ReplyInputs"
    social_decision: "ReplyStrategyDecision"
    current_time: "datetime"


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
    reply_compose_input: "AIRuntimeComposeInput | None" = None
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
    commit_status: str = "committed"
    substeps: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeTraceOutcome:
    """Trace projection for a terminal generated or non-generated turn."""

    stage: RuntimeStageName
    trace: TurnTrace
    context: TurnContext | None = None
    social_decision: "ReplyStrategyDecision | None" = None


@runtime_checkable
class RuntimePolicyStage(Protocol):
    """Deterministic and social policy boundary for one turn."""

    def evaluate(
        self,
        *,
        request: "AIRuntimeReplyRequest",
        wake_context: "WakeContext",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimePolicyOutcome: ...

    async def decide_reply(
        self,
        *,
        request: "AIRuntimeReplyRequest",
        wake_context: "WakeContext",
        context: RuntimeContextBundle,
        current_time: "datetime",
        trace_id: str,
    ) -> Any: ...


@runtime_checkable
class RuntimeObservationStage(Protocol):
    """Live observation side-effect boundary before read context assembly."""

    async def apply(
        self,
        *,
        request: "AIRuntimeReplyRequest",
        current_time: "datetime",
    ) -> None: ...


@runtime_checkable
class RuntimeContextStage(Protocol):
    """Read-oriented context assembly boundary for one turn."""

    async def assemble(
        self,
        *,
        request: "AIRuntimeReplyRequest",
        current_time: "datetime",
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

    async def commit(  # noqa: PLR0913
        self,
        *,
        request: "AIRuntimeReplyRequest",
        inputs: Any,
        social_decision: Any,
        plan: RuntimeTurnPlan,
        generation: RuntimeExecutionOutcome,
        trace_id: str,
        hard_decision: RuntimeHardRuleDecision,
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult: ...


@runtime_checkable
class RuntimeTraceStage(Protocol):
    """Terminal compact trace projection and persistence boundary."""

    def project(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        request: "AIRuntimeReplyRequest",
        strategy_decision: RuntimeHardRuleDecision,
        turn_result: "AgentTurnResult | None",
        delivery_result: "DeliveryOutcome | None" = None,
        commit_status: str | None = None,
    ) -> RuntimeTraceOutcome: ...


__all__ = [
    "RuntimeCommitResult",
    "RuntimeCommitStage",
    "RuntimeContextBundle",
    "RuntimeContextStage",
    "RuntimeExecutionOutcome",
    "RuntimeExecutionStage",
    "RuntimeObservationStage",
    "RuntimePlanningInput",
    "RuntimePlanningStage",
    "RuntimePolicyOutcome",
    "RuntimePolicyStage",
    "RuntimeStageName",
    "RuntimeTraceOutcome",
    "RuntimeTraceStage",
    "RuntimeTurnPlan",
]
