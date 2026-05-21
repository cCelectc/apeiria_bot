"""AI runtime coordinator and explicit runtime paths."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal, NoReturn, Protocol

from nonebot.log import logger

from .context.adapter import build_turn_context
from .observation import classify_observation_level
from .policy import social_skip_to_runtime_decision
from .session.context import (
    DeliveryTarget,
    RuntimeTurnInput,
    TurnContext,
)
from .stages import (
    RuntimeCommitInput,
    RuntimeCommitResult,
    RuntimeCommitStage,
    RuntimeContextBundle,
    RuntimeContextStage,
    RuntimeExecutionOutcome,
    RuntimeExecutionStage,
    RuntimeIngressInput,
    RuntimeObservationStage,
    RuntimePlanningInput,
    RuntimePlanningStage,
    RuntimePolicyOutcome,
    RuntimePolicyStage,
    RuntimeSocialDecisionInput,
    RuntimeTraceInput,
    RuntimeTraceOutcome,
    RuntimeTraceStage,
    RuntimeTurnPlan,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.contracts import RuntimeTraceContext


class RuntimeStageNotConfiguredError(RuntimeError):
    """Raised when a runtime path helper is called without its stage."""


class _UnavailableRuntimeStage:
    def _raise(self) -> NoReturn:
        raise RuntimeStageNotConfiguredError

    def evaluate(self, **_: Any) -> RuntimePolicyOutcome:
        self._raise()

    async def decide_reply(self, **_: Any) -> Any:
        self._raise()

    async def apply(self, **_: Any) -> None:
        self._raise()

    async def apply_observed_turn(self, **_: Any) -> None:
        self._raise()

    async def apply_deep_observation(self, **_: Any) -> Any:
        self._raise()

    async def assemble(self, **_: Any) -> RuntimeContextBundle:
        self._raise()

    async def plan(self, **_: Any) -> RuntimeTurnPlan | None:
        self._raise()

    async def execute(self, **_: Any) -> RuntimeExecutionOutcome:
        self._raise()

    async def commit(self, **_: Any) -> RuntimeCommitResult:
        self._raise()

    def project(self, **_: Any) -> RuntimeTraceOutcome:
        self._raise()


@dataclass(frozen=True, slots=True)
class RuntimeStageReport:
    """Compact public summary for one runtime stage."""

    stage: str
    status: str
    diagnostics: dict[str, object] = field(default_factory=dict)


RuntimeOutcome = Literal[
    "hard_rule_skipped",
    "observed",
    "social_no_reply",
    "no_plan",
    "no_model",
    "empty_response",
    "execution_failed",
    "commit_failed",
    "committed",
]


@dataclass(frozen=True, slots=True)
class AIRuntimeResult:
    """Result envelope returned by AI runtime coordination."""

    trace_id: str
    path: str
    outcome: RuntimeOutcome
    commit: RuntimeCommitResult | None = None
    stage_reports: tuple[RuntimeStageReport, ...] = ()
    diagnostics: dict[str, object] = field(default_factory=dict)

    @property
    def reply_text(self) -> str | None:
        """Return the committed reply text when the runtime produced one."""

        return self.commit.reply_text if self.commit is not None else None


@dataclass(frozen=True, slots=True)
class AIRuntimeRequest:
    """Base request submitted to the AI runtime coordinator."""

    trace_id: str
    trace: "RuntimeTraceContext"
    turn: RuntimeTurnInput
    current_time: "datetime"
    session_runtime: Any | None = None
    wake_context: "WakeContext | None" = None

    @property
    def path_name(self) -> str:
        """Return the runtime path name requested by this work item."""

        return "reply"


@dataclass(frozen=True, slots=True)
class ReplyRuntimeRequest(AIRuntimeRequest):
    """Runtime request for a reply-capable turn."""


class RuntimePath(Protocol):
    """Named runtime path executed by the coordinator."""

    @property
    def name(self) -> str:
        """Return the stable path name used by the coordinator."""
        ...

    async def run(self, request: AIRuntimeRequest) -> AIRuntimeResult:
        """Run one normalized runtime request."""
        ...


@dataclass(frozen=True, slots=True)
class ReplyPath:
    """Run one reply-capable turn through the runtime stages."""

    policy_stage: RuntimePolicyStage = field(default_factory=_UnavailableRuntimeStage)
    observation_stage: RuntimeObservationStage = field(
        default_factory=_UnavailableRuntimeStage
    )
    context_stage: RuntimeContextStage = field(default_factory=_UnavailableRuntimeStage)
    planning_stage: RuntimePlanningStage = field(
        default_factory=_UnavailableRuntimeStage
    )
    execution_stage: RuntimeExecutionStage = field(
        default_factory=_UnavailableRuntimeStage
    )
    commit_stage: RuntimeCommitStage = field(default_factory=_UnavailableRuntimeStage)
    trace_stage: RuntimeTraceStage = field(default_factory=_UnavailableRuntimeStage)
    name: str = "reply"

    async def run(self, request: AIRuntimeRequest) -> AIRuntimeResult:
        """Run a reply-capable runtime request."""

        return await self._run_reply_path(
            trace_id=request.trace_id,
            trace=request.trace,
            turn=request.turn,
            wake_context=request.wake_context,
            current_time=request.current_time,
            session_runtime=request.session_runtime,
        )

    async def _run_reply_path(  # noqa: PLR0913, PLR0915
        self,
        *,
        trace_id: str,
        trace: Any,
        turn: RuntimeTurnInput,
        wake_context: "WakeContext | None",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> AIRuntimeResult:
        """Run one reply turn through policy, context, planning, execution, commit."""

        stage_reports: list[RuntimeStageReport] = []
        identity = turn.identity
        wake_context = wake_context or self._build_fallback_wake_context(turn)
        ingress_input = RuntimeIngressInput(
            stage="ingress",
            turn=turn,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )
        policy = self.evaluate_policy(
            ingress_input=ingress_input,
        )
        stage_reports.append(
            RuntimeStageReport(
                stage="policy",
                status="continue" if policy.should_continue else "skipped",
                diagnostics={
                    "action": policy.decision.action,
                    "reason_codes": policy.decision.reason_codes,
                },
            )
        )
        hard_decision = policy.decision
        observation_level = classify_observation_level(hard_decision)
        if not policy.should_continue:
            await self._apply_pre_context_observation(
                ingress_input=ingress_input,
                observation_level=observation_level,
                persist_light_turn=True,
            )
            logger.debug(
                "AI trace {} skipped reply: hard_rule for session {} action={} "
                "reason_codes={}",
                trace_id,
                identity.session_id,
                hard_decision.action,
                hard_decision.reason_codes,
            )
            self.project_trace(
                trace_input=RuntimeTraceInput(
                    stage="trace",
                    trace_id=trace_id,
                    turn=turn,
                    strategy_decision=hard_decision,
                    turn_result=None,
                ),
            )
            stage_reports.append(
                RuntimeStageReport(
                    stage="observation",
                    status=observation_level,
                )
            )
            stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
            return self._result(
                trace_id=trace_id,
                outcome="hard_rule_skipped",
                stage_reports=stage_reports,
                turn=turn,
            )

        ingress_input = await self._apply_pre_context_observation(
            ingress_input=ingress_input,
            observation_level=observation_level,
            persist_light_turn=False,
        )
        await self.apply_observation_side_effects(ingress_input=ingress_input)
        stage_reports.append(
            RuntimeStageReport(
                stage="observation",
                status=observation_level,
            )
        )
        turn = ingress_input.turn
        context_bundle = await self.assemble_context(
            ingress_input=ingress_input,
        )
        context = context_bundle.context
        stage_reports.append(
            RuntimeStageReport(
                stage="context",
                status="assembled",
                diagnostics={
                    "recalled_memory_count": len(context.recalled_memories),
                    "context_diagnostics": context_bundle.diagnostics,
                },
            )
        )
        social_decision = await self.policy_stage.decide_reply(
            social_input=RuntimeSocialDecisionInput(
                stage="policy",
                trace_id=trace_id,
                turn=turn,
                wake_context=wake_context,
                context=context_bundle,
                current_time=current_time,
            ),
        )
        stage_reports.append(
            RuntimeStageReport(
                stage="policy",
                status="speak" if social_decision.should_speak else "no_reply",
                diagnostics={
                    "reply_policy": "social",
                    "reason": getattr(social_decision, "reason", None),
                },
            )
        )
        if not social_decision.should_speak:
            runtime_decision = social_skip_to_runtime_decision(social_decision)
            logger.debug(
                "AI trace {} skipped reply: strategy_skipped for session {} "
                "action={} reason_codes={}",
                trace_id,
                identity.session_id,
                runtime_decision.action,
                runtime_decision.reason_codes,
            )
            self.project_trace(
                trace_input=RuntimeTraceInput(
                    stage="trace",
                    trace_id=trace_id,
                    turn=turn,
                    strategy_decision=runtime_decision,
                    turn_result=None,
                ),
            )
            stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
            return self._result(
                trace_id=trace_id,
                outcome="social_no_reply",
                stage_reports=stage_reports,
                turn=turn,
                context=context,
            )

        plan = await self.plan_turn(
            trace_id=trace_id,
            turn=turn,
            context=context,
            social_decision=social_decision,
            current_time=current_time,
        )
        if plan is None:
            self.project_trace(
                trace_input=RuntimeTraceInput(
                    stage="trace",
                    trace_id=trace_id,
                    turn=turn,
                    strategy_decision=hard_decision,
                    turn_result=None,
                ),
            )
            stage_reports.append(RuntimeStageReport(stage="planning", status="no_plan"))
            stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
            return self._result(
                trace_id=trace_id,
                outcome="no_plan",
                stage_reports=stage_reports,
                turn=turn,
                context=context,
            )
        stage_reports.append(
            RuntimeStageReport(
                stage="planning",
                status="planned",
                diagnostics=_plan_diagnostics(plan),
            )
        )

        turn_context = build_turn_context(
            trace_id=trace_id,
            turn=turn,
            context=context,
            hard_decision=hard_decision,
            social_decision=social_decision,
            delivery_target=_delivery_target_for_turn(turn),
            prompt_messages=plan.prompt_messages,
            tool_exposure_plan=plan.tool_exposure_plan,
            current_time=current_time,
            prompt_diagnostics=plan.prompt_diagnostics,
        )
        execution = await self.execute_turn(turn_context=turn_context, plan=plan)
        stage_reports.append(
            RuntimeStageReport(
                stage="execution",
                status="executed",
                diagnostics={
                    "tool_observation_count": len(execution.tool_runtime.turns),
                    "has_response": execution.response is not None,
                },
            )
        )
        response = execution.response
        if response is None or not response.content.strip():
            logger.debug(
                "AI trace {} skipped reply: empty model response for session {} "
                "entry_kind={} entry_trigger={}",
                trace_id,
                identity.session_id,
                trace.kind,
                trace.trigger,
            )
            self.project_trace(
                trace_input=RuntimeTraceInput(
                    stage="trace",
                    trace_id=trace_id,
                    turn=turn,
                    strategy_decision=hard_decision,
                    turn_result=execution.turn_result,
                    delivery_result=execution.delivery_result,
                ),
            )
            stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
            return self._result(
                trace_id=trace_id,
                outcome="empty_response",
                stage_reports=stage_reports,
                turn=turn,
                context=context,
                routing_diagnostics=plan.routing_diagnostics,
                delivery_status=_delivery_status_for_result(
                    execution.delivery_result,
                ),
            )

        commit = await self.commit_turn(
            commit_input=RuntimeCommitInput(
                stage="commit",
                trace_id=trace_id,
                turn=turn,
                context=context,
                social_decision=social_decision,
                plan=plan,
                generation=execution,
                hard_decision=hard_decision,
                current_time=current_time,
                session_runtime=session_runtime,
            ),
        )
        stage_reports.append(
            RuntimeStageReport(
                stage="commit",
                status=commit.commit_status,
                diagnostics={
                    "delivery_status": _delivery_status_for_result(
                        commit.delivery_result,
                    ),
                },
            )
        )
        trace_outcome = self.project_trace(
            trace_input=RuntimeTraceInput(
                stage="trace",
                trace_id=trace_id,
                turn=turn,
                strategy_decision=hard_decision,
                turn_result=execution.turn_result,
                delivery_result=commit.delivery_result,
                commit_status=commit.commit_status,
            ),
        )
        commit = _with_commit_substep(commit, name="trace", status="committed")
        if commit.commit_status == "failed":
            stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
            return self._result(
                trace_id=trace_id,
                outcome="commit_failed",
                commit=commit,
                stage_reports=stage_reports,
                turn=turn,
                context=context,
                selected_model_ref=_selected_model_ref(plan),
                routing_diagnostics=plan.routing_diagnostics,
                tool_exposure_summary=_tool_exposure_summary(plan),
                delivery_status=_delivery_status_for_result(commit.delivery_result),
            )
        logger.info(
            "AI trace {} generated {} reply for session {} with source={} "
            "model={} memories={} tool_observations={} entry_kind={} "
            "entry_trigger={}",
            trace_id,
            turn.runtime_mode,
            identity.session_id,
            response.source_id,
            response.model_name,
            len(context.recalled_memories),
            len(execution.tool_runtime.turns),
            trace.kind,
            trace.trigger,
        )
        stage_reports.append(RuntimeStageReport(stage="trace", status="projected"))
        return self._result(
            trace_id=trace_id,
            outcome="committed",
            commit=replace(commit, trace=trace_outcome.trace),
            stage_reports=stage_reports,
            turn=turn,
            context=context,
            selected_model_ref=_selected_model_ref(plan),
            routing_diagnostics=plan.routing_diagnostics,
            tool_exposure_summary=_tool_exposure_summary(plan),
            delivery_status=_delivery_status_for_result(commit.delivery_result),
        )

    def evaluate_policy(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimePolicyOutcome:
        """Evaluate deterministic runtime policy for one turn."""

        return self.policy_stage.evaluate(
            ingress_input=ingress_input,
        )

    async def apply_observation_side_effects(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> None:
        """Apply live observation writes outside read-oriented context assembly."""

        await self.observation_stage.apply(
            ingress_input=ingress_input,
        )

    async def apply_observed_turn(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> None:
        """Persist non-reply observed turns through the observation boundary."""

        await self.observation_stage.apply_observed_turn(
            ingress_input=ingress_input,
        )

    async def apply_deep_observation(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> Any:
        """Run governed deep observation before read-oriented context assembly."""

        return await self.observation_stage.apply_deep_observation(
            ingress_input=ingress_input,
        )

    async def _apply_pre_context_observation(
        self,
        *,
        ingress_input: RuntimeIngressInput,
        observation_level: str,
        persist_light_turn: bool,
    ) -> RuntimeIngressInput:
        if observation_level == "observe_deep":
            ingress_input = await self._apply_deep_observation_result(
                ingress_input=ingress_input,
            )
            await self.apply_observed_turn(ingress_input=ingress_input)
            return ingress_input
        if observation_level == "engage":
            return await self._apply_deep_observation_result(
                ingress_input=ingress_input,
            )
        if observation_level == "observe_light" and persist_light_turn:
            await self.apply_observed_turn(ingress_input=ingress_input)
        return ingress_input

    async def _apply_deep_observation_result(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimeIngressInput:
        extraction_result = await self.apply_deep_observation(
            ingress_input=ingress_input,
        )
        if extraction_result is None:
            return ingress_input
        return replace(
            ingress_input,
            turn=replace(
                ingress_input.turn,
                sentiment=extraction_result.sentiment,
            ),
        )

    async def assemble_context(
        self,
        *,
        ingress_input: RuntimeIngressInput,
    ) -> RuntimeContextBundle:
        """Gather prompt-facing context materials for one turn."""

        return await self.context_stage.assemble(
            ingress_input=ingress_input,
        )

    async def plan_turn(
        self,
        *,
        trace_id: str,
        turn: RuntimeTurnInput,
        context: Any,
        social_decision: Any,
        current_time: "datetime",
    ) -> RuntimeTurnPlan | None:
        """Build the runtime-owned plan consumed by execution."""

        return await self.planning_stage.plan(
            planning_input=RuntimePlanningInput(
                stage="planning",
                trace_id=trace_id,
                turn=turn,
                context=context,
                social_decision=social_decision,
                current_time=current_time,
            ),
        )

    async def execute_turn(
        self,
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome:
        """Execute one direct or tool-capable turn."""

        return await self.execution_stage.execute(
            turn_context=turn_context,
            plan=plan,
        )

    async def commit_turn(
        self,
        *,
        commit_input: RuntimeCommitInput,
    ) -> RuntimeCommitResult:
        """Persist one generated turn through the commit stage."""

        return await self.commit_stage.commit(
            commit_input=commit_input,
        )

    def project_trace(
        self,
        *,
        trace_input: RuntimeTraceInput,
    ) -> RuntimeTraceOutcome:
        """Project one terminal generated or non-generated outcome."""

        return self.trace_stage.project(
            trace_input=trace_input,
        )

    @staticmethod
    def _build_fallback_wake_context(turn: RuntimeTurnInput) -> "WakeContext":
        from apeiria.app.ai.runtime.planning.wake import (
            build_fallback_wake_context,
        )

        return build_fallback_wake_context(turn)

    def _result(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        outcome: RuntimeOutcome,
        stage_reports: list[RuntimeStageReport],
        turn: RuntimeTurnInput,
        commit: RuntimeCommitResult | None = None,
        context: Any | None = None,
        selected_model_ref: str | None = None,
        routing_diagnostics: dict[str, object] | None = None,
        tool_exposure_summary: dict[str, object] | None = None,
        delivery_status: str | None = None,
    ) -> AIRuntimeResult:
        diagnostics: dict[str, object] = {
            "path": self.name,
            "outcome": outcome,
            "runtime_mode": turn.runtime_mode,
            "stage_count": len(stage_reports),
        }
        if selected_model_ref is not None:
            diagnostics["selected_model"] = selected_model_ref
        if routing_diagnostics:
            diagnostics["model_routing"] = routing_diagnostics
        if tool_exposure_summary:
            diagnostics["tool_exposure"] = tool_exposure_summary
        if context is not None:
            diagnostics["recalled_memory_count"] = len(context.recalled_memories)
            rag_diagnostics = getattr(context, "rag_diagnostics", None)
            degradation_reason = getattr(rag_diagnostics, "degradation_reason", None)
            if degradation_reason is not None:
                diagnostics["rag_degradation_reason"] = degradation_reason
        if delivery_status is not None:
            diagnostics["delivery_status"] = delivery_status
        return AIRuntimeResult(
            trace_id=trace_id,
            path=self.name,
            outcome=outcome,
            commit=commit,
            stage_reports=tuple(stage_reports),
            diagnostics=diagnostics,
        )


@dataclass(frozen=True, slots=True)
class AIRuntimeCoordinator:
    """Select and run explicit AI runtime paths."""

    paths: Mapping[str, RuntimePath] = field(default_factory=dict)

    async def run(self, request: AIRuntimeRequest) -> AIRuntimeResult:
        """Run one normalized AI runtime request."""

        path = self._resolve_path(request)
        if _should_serialize_in_coordinator(request.session_runtime):
            runtime = request.session_runtime
            assert runtime is not None

            async def operation() -> AIRuntimeResult:
                return await path.run(request)

            return await runtime.run_serialized(operation, now=request.current_time)
        return await path.run(request)

    def _resolve_path(self, request: AIRuntimeRequest) -> RuntimePath:
        path = self.paths.get(request.path_name)
        if path is None:
            raise RuntimePathNotConfiguredError(request.path_name)
        return path


class RuntimePathNotConfiguredError(RuntimeError):
    """Raised when no runtime path is registered for a request."""

    def __init__(self, path_name: str) -> None:
        super().__init__(f"AI runtime path is not configured: {path_name}")


def _delivery_target_for_turn(turn: RuntimeTurnInput) -> DeliveryTarget:
    if turn.runtime_mode == "future_task":
        return DeliveryTarget(
            session_id=turn.identity.session_id,
            delivery_channel="future_task",
        )
    return DeliveryTarget(
        session_id=turn.identity.session_id,
        reply_to_message_id=turn.source_message_id,
        delivery_channel="message",
    )


def _with_commit_substep(
    commit: RuntimeCommitResult,
    *,
    name: str,
    status: str,
) -> RuntimeCommitResult:
    return replace(commit, substeps={**commit.substeps, name: status})


def _plan_diagnostics(plan: RuntimeTurnPlan) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "selected_model": _selected_model_ref(plan),
        "fallback_model_count": len(plan.fallback_models),
        "tool_exposure": _tool_exposure_summary(plan),
    }
    if plan.routing_diagnostics:
        diagnostics["model_routing"] = plan.routing_diagnostics
    return diagnostics


def _selected_model_ref(plan: RuntimeTurnPlan) -> str:
    model_name = plan.selected.resolved_model_name or plan.selected.profile.model_id
    return (
        f"{plan.selected.source.source_id}:"
        f"{plan.selected.profile.profile_id}:"
        f"{model_name}"
    )


def _tool_exposure_summary(plan: RuntimeTurnPlan) -> dict[str, object]:
    tool_plan = plan.tool_exposure_plan
    summary: dict[str, object] = {
        "selected_tool_count": len(tool_plan.selected_tool_names),
        "has_executable_tools": tool_plan.has_executable_tools,
    }
    allowed_tool_count = tool_plan.diagnostics.get("allowed_tool_count")
    if isinstance(allowed_tool_count, int):
        summary["allowed_tool_count"] = allowed_tool_count
    return summary


def _delivery_status_for_result(delivery_result: object | None) -> str:
    if delivery_result is None:
        return "not_required"
    delivered = getattr(delivery_result, "delivered", None)
    if delivered is True:
        return "delivered"
    if delivered is False:
        return "failed"
    return "unknown"


def _should_serialize_in_coordinator(session_runtime: Any | None) -> bool:
    if session_runtime is None or not hasattr(session_runtime, "run_serialized"):
        return False
    return not bool(getattr(session_runtime, "current_turn_owns_lock", False))


__all__ = [
    "AIRuntimeCoordinator",
    "AIRuntimeRequest",
    "AIRuntimeResult",
    "ReplyPath",
    "ReplyRuntimeRequest",
    "RuntimeOutcome",
    "RuntimePath",
    "RuntimePathNotConfiguredError",
    "RuntimeStageReport",
]
