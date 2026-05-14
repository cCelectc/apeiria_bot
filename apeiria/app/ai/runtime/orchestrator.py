"""Session runtime turn engine with explicit stage boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, NoReturn

from nonebot.log import logger

from .context.adapter import build_turn_context
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
    from datetime import datetime

    from apeiria.app.ai.reply_strategy.models import WakeContext


class RuntimeStageNotConfiguredError(RuntimeError):
    """Raised when a turn engine helper is called without its stage."""


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
class AISessionTurnEngine:
    """Coordinate one normalized AI turn through named runtime stages."""

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

    async def run_reply_turn(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: Any,
        turn: RuntimeTurnInput,
        wake_context: "WakeContext | None",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult | None:
        """Run one reply turn, owning same-session serialization when available."""

        if _should_serialize_in_engine(session_runtime):
            runtime = session_runtime
            assert runtime is not None

            async def operation() -> RuntimeCommitResult | None:
                return await self._run_reply_turn_steps(
                    trace_id=trace_id,
                    trace=trace,
                    turn=turn,
                    wake_context=wake_context,
                    current_time=current_time,
                    session_runtime=session_runtime,
                )

            return await runtime.run_serialized(operation, now=current_time)

        return await self._run_reply_turn_steps(
            trace_id=trace_id,
            trace=trace,
            turn=turn,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )

    async def _run_reply_turn_steps(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: Any,
        turn: RuntimeTurnInput,
        wake_context: "WakeContext | None",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult | None:
        """Run one reply turn through policy, context, planning, execution, commit."""

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
        hard_decision = policy.decision
        if not policy.should_continue:
            if hard_decision.action == "observe" and hard_decision.should_observe:
                await self.apply_observed_turn(
                    ingress_input=ingress_input,
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
            return None

        await self.apply_observation_side_effects(
            ingress_input=ingress_input,
        )
        context_bundle = await self.assemble_context(
            ingress_input=ingress_input,
        )
        context = context_bundle.context
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
            return None

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
            return None

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
            return None

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
            return None
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
        return replace(commit, trace=trace_outcome.trace)

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


def _should_serialize_in_engine(session_runtime: Any | None) -> bool:
    if session_runtime is None or not hasattr(session_runtime, "run_serialized"):
        return False
    return not bool(getattr(session_runtime, "current_turn_owns_lock", False))


__all__ = [
    "AISessionTurnEngine",
]
