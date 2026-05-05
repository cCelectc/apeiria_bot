"""Session runtime turn engine with explicit stage boundaries."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, NoReturn

from nonebot.log import logger

from .context import DeliveryTarget, RuntimeTurnSource
from .context_adapter import build_turn_context
from .execution import execute_runtime_turn
from .hard_rules import decide_runtime_hard_rule, map_legacy_skip_to_runtime_decision
from .planning import plan_runtime_turn
from .stages import (
    RuntimeCommitResult,
    RuntimeCommitStage,
    RuntimeContextBundle,
    RuntimeContextStage,
    RuntimeExecutionOutcome,
    RuntimeExecutionStage,
    RuntimeObservationStage,
    RuntimePlanningStage,
    RuntimePolicyOutcome,
    RuntimePolicyStage,
    RuntimeTraceOutcome,
    RuntimeTraceStage,
    RuntimeTurnPlan,
)
from .trace import project_turn_trace

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.session_runtime.strategy import RuntimeHardRuleDecision


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
class DefaultRuntimePolicyStage:
    """Policy stage backed by runtime hard rules and reply strategy."""

    reply_decider: Any

    def evaluate(
        self,
        *,
        request: Any,
        wake_context: "WakeContext",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimePolicyOutcome:
        identity = request.identity
        source = RuntimeTurnSource(
            runtime_mode=request.runtime_mode,
            message_text=request.message_text,
            source_message_id=request.source_message_id,
            user_id=request.user_id,
            direct_signal=request.is_tome,
            is_private=identity.scene_type == "private",
            event_dedupe_key=request.event_dedupe_key,
            event_dedupe_claimed=request.event_dedupe_claimed,
        )
        return RuntimePolicyOutcome(
            stage="policy",
            source=source,
            decision=decide_runtime_hard_rule(
                wake_context=wake_context,
                source=source,
                session_runtime=session_runtime,
                now=current_time,
            ),
        )

    async def decide_reply(
        self,
        *,
        request: Any,
        wake_context: "WakeContext",
        context: RuntimeContextBundle,
        current_time: "datetime",
        trace_id: str,
    ) -> Any:
        inputs = context.inputs
        return await self.reply_decider(
            request=request,
            wake_context=wake_context,
            turns=inputs.turns,
            conversation_summary=inputs.conversation_summary,
            relationship_context=inputs.relationship_context,
            persona=inputs.persona,
            allowed_tools=inputs.allowed_tools,
            initiative_bias=inputs.initiative_bias,
            model_target=inputs.model_target,
            current_time=current_time,
            trace_id=trace_id,
        )


@dataclass(frozen=True, slots=True)
class DefaultRuntimeObservationStage:
    """Observation side-effect stage for live writes before context reads."""

    apply_observation_effects: Any | None = None

    async def apply(
        self,
        *,
        request: Any,
        current_time: "datetime",
    ) -> None:
        if self.apply_observation_effects is None:
            return
        await self.apply_observation_effects(
            request=request,
            current_time=current_time,
        )


@dataclass(frozen=True, slots=True)
class DefaultRuntimeContextStage:
    """Context assembly stage backed by the reply input collector."""

    gather_reply_inputs: Any

    async def assemble(
        self,
        *,
        request: Any,
        current_time: "datetime",
    ) -> RuntimeContextBundle:
        inputs = await self.gather_reply_inputs(request, current_time)
        return RuntimeContextBundle(stage="context", inputs=inputs)


@dataclass(frozen=True, slots=True)
class DefaultRuntimePlanningStage:
    """Plan prompt/model/tool materials for execution."""

    prepare_generation: Any = plan_runtime_turn

    async def plan(
        self,
        *,
        trace_id: str,
        request: Any,
        inputs: Any,
        social_decision: Any,
        current_time: "datetime",
    ) -> RuntimeTurnPlan | None:
        return await self.prepare_generation(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
            trace_id=trace_id,
        )


@dataclass(frozen=True, slots=True)
class DefaultRuntimeExecutionStage:
    """Run the model/tool execution path for a planned turn."""

    async def execute(
        self,
        *,
        turn_context: Any,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome:
        return await execute_runtime_turn(
            turn_context=turn_context,
            plan=plan,
        )


@dataclass(frozen=True, slots=True)
class DefaultRuntimeCommitStage:
    """Commit post-execution side effects with structured substep status."""

    reply_persistence: Any
    reply_strategy_service: Any
    deliver_reply: Any | None = None
    record_context_usage: Any | None = None

    async def commit(  # noqa: PLR0913
        self,
        *,
        request: Any,
        inputs: Any,
        social_decision: Any,
        plan: RuntimeTurnPlan,
        generation: RuntimeExecutionOutcome,
        trace_id: str,
        hard_decision: "RuntimeHardRuleDecision",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult:
        response = generation.response
        reply_text = response.content.strip() if response is not None else ""
        substeps: dict[str, str] = {}
        commit_status = "committed"

        delivery_result = await self._commit_delivery(
            request=request,
            reply_text=reply_text,
            trace_id=trace_id,
        )
        if delivery_result is None:
            substeps["delivery"] = "not_required"
        elif delivery_result.delivered:
            substeps["delivery"] = "committed"
        else:
            substeps["delivery"] = "failed"
            commit_status = "partial"

        generation_with_delivery = replace(generation, delivery_result=delivery_result)
        required_failed = await self._commit_required_persistence(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            plan=plan,
            generation=generation_with_delivery,
            trace_id=trace_id,
            substeps=substeps,
        )
        if required_failed:
            return RuntimeCommitResult(
                stage="commit",
                reply_text="",
                delivery_result=delivery_result,
                commit_status="failed",
                substeps=substeps,
            )

        await self._commit_context_window(
            request=request,
            substeps=substeps,
        )
        self._commit_reply_accounting(
            request=request,
            response=response,
            inputs=inputs,
            generation=generation_with_delivery,
            hard_decision=hard_decision,
            current_time=current_time,
            session_runtime=session_runtime,
            substeps=substeps,
        )
        if any(status == "failed" for status in substeps.values()):
            commit_status = "partial"
        return RuntimeCommitResult(
            stage="commit",
            reply_text=reply_text,
            delivery_result=delivery_result,
            commit_status=commit_status,
            substeps=substeps,
        )

    async def _commit_delivery(
        self,
        *,
        request: Any,
        reply_text: str,
        trace_id: str,
    ) -> Any | None:
        if self.deliver_reply is None:
            return None
        result = self.deliver_reply(
            request,
            reply_text,
            trace_id=trace_id,
        )
        if inspect.isawaitable(result):
            return await result
        return result

    async def _commit_required_persistence(  # noqa: PLR0913
        self,
        *,
        request: Any,
        inputs: Any,
        social_decision: Any,
        plan: RuntimeTurnPlan,
        generation: RuntimeExecutionOutcome,
        trace_id: str,
        substeps: dict[str, str],
    ) -> bool:
        try:
            status = await self.reply_persistence.persist_tool_observations(
                request=request,
                generation=generation,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace {} failed tool-observation persistence for session {}",
                trace_id,
                request.identity.session_id,
            )
            substeps["tool_observations"] = "failed"
            return True
        substeps["tool_observations"] = status

        try:
            await self.reply_persistence.persist_assistant_message(
                request=request,
                inputs=inputs,
                social_decision=social_decision,
                plan=plan,
                generation=generation,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace {} failed assistant persistence for session {}",
                trace_id,
                request.identity.session_id,
            )
            substeps["assistant_message"] = "failed"
            return True
        substeps["assistant_message"] = "committed"
        return False

    async def _commit_context_window(
        self,
        *,
        request: Any,
        substeps: dict[str, str],
    ) -> None:
        try:
            await self.reply_persistence.rebuild_context_window(
                identity=request.identity,
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI context-window rebuild failed for session {}",
                request.identity.session_id,
            )
            substeps["context_window"] = "failed"
            return
        substeps["context_window"] = "committed"

    def _commit_reply_accounting(  # noqa: PLR0913
        self,
        *,
        request: Any,
        response: Any | None,
        inputs: Any,
        generation: RuntimeExecutionOutcome,
        hard_decision: "RuntimeHardRuleDecision",
        current_time: "datetime",
        session_runtime: Any | None,
        substeps: dict[str, str],
    ) -> None:
        try:
            if self.record_context_usage is not None and response is not None:
                self.record_context_usage(
                    request.identity.session_id,
                    response=response,
                    message_count=len(inputs.turns),
                )
            if (
                generation.delivery_result is None
                or generation.delivery_result.delivered
            ):
                self.reply_strategy_service.notify_replied(request.identity.session_id)
                if session_runtime is not None and hard_decision.reason_codes == (
                    "ambient_candidate",
                ):
                    session_runtime.record_ambient_reply(now=current_time)
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning(
                "AI trace accounting failed for session {}",
                request.identity.session_id,
            )
            substeps["reply_accounting"] = "failed"
            return
        substeps["reply_accounting"] = "committed"


@dataclass(frozen=True, slots=True)
class DefaultRuntimeTraceStage:
    """Project and durably store compact terminal turn traces."""

    trace_observer: Any | None = None
    trace_store: Any | None = None

    def project(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        request: Any,
        strategy_decision: "RuntimeHardRuleDecision",
        turn_result: "AgentTurnResult | None",
        delivery_result: "DeliveryOutcome | None" = None,
        commit_status: str | None = None,
    ) -> RuntimeTraceOutcome:
        outcome = RuntimeTraceOutcome(
            stage="trace",
            trace=project_turn_trace(
                session_id=request.identity.session_id,
                strategy_decision=strategy_decision,
                turn_result=turn_result,
                trace_id=trace_id,
                runtime_mode=request.runtime_mode,
                delivery_result=delivery_result,
            ),
        )
        if self.trace_observer is not None:
            self.trace_observer(outcome)
        if self.trace_store is not None:
            self.trace_store.store_trace(outcome.trace, commit_status=commit_status)
        return outcome


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
        request: Any,
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
                    request=request,
                    wake_context=wake_context,
                    current_time=current_time,
                    session_runtime=session_runtime,
                )

            return await runtime.run_serialized(operation, now=current_time)

        return await self._run_reply_turn_steps(
            trace_id=trace_id,
            trace=trace,
            request=request,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )

    async def _run_reply_turn_steps(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: Any,
        request: Any,
        wake_context: "WakeContext | None",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult | None:
        """Run one reply turn through policy, context, planning, execution, commit."""

        identity = request.identity
        wake_context = wake_context or self._build_fallback_wake_context(request)
        policy = self.evaluate_policy(
            request=request,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )
        hard_decision = policy.decision
        if not policy.should_continue:
            logger.debug(
                "AI trace {} skipped reply: hard_rule for session {} action={} "
                "reason_codes={}",
                trace_id,
                identity.session_id,
                hard_decision.action,
                hard_decision.reason_codes,
            )
            self.project_trace(
                trace_id=trace_id,
                request=request,
                strategy_decision=hard_decision,
                turn_result=None,
            )
            return None

        await self.apply_observation_side_effects(
            request=request,
            current_time=current_time,
        )
        context_bundle = await self.assemble_context(
            request=request,
            current_time=current_time,
        )
        inputs = context_bundle.inputs
        social_decision = await self.policy_stage.decide_reply(
            request=request,
            wake_context=wake_context,
            context=context_bundle,
            current_time=current_time,
            trace_id=trace_id,
        )
        if not social_decision.should_speak:
            runtime_decision = map_legacy_skip_to_runtime_decision(social_decision)
            logger.debug(
                "AI trace {} skipped reply: strategy_skipped for session {} "
                "action={} reason_codes={}",
                trace_id,
                identity.session_id,
                runtime_decision.action,
                runtime_decision.reason_codes,
            )
            self.project_trace(
                trace_id=trace_id,
                request=request,
                strategy_decision=runtime_decision,
                turn_result=None,
            )
            return None

        plan = await self.plan_turn(
            trace_id=trace_id,
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
        )
        if plan is None:
            self.project_trace(
                trace_id=trace_id,
                request=request,
                strategy_decision=hard_decision,
                turn_result=None,
            )
            return None

        turn_context = build_turn_context(
            trace_id=trace_id,
            request=request,
            inputs=inputs,
            hard_decision=hard_decision,
            social_decision=social_decision,
            delivery_target=_delivery_target_for_request(request),
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
                trace_id=trace_id,
                request=request,
                strategy_decision=hard_decision,
                turn_result=execution.turn_result,
                delivery_result=execution.delivery_result,
            )
            return None

        commit = await self.commit_turn(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            plan=plan,
            generation=execution,
            trace_id=trace_id,
            hard_decision=hard_decision,
            current_time=current_time,
            session_runtime=session_runtime,
        )
        trace_outcome = self.project_trace(
            trace_id=trace_id,
            request=request,
            strategy_decision=hard_decision,
            turn_result=execution.turn_result,
            delivery_result=commit.delivery_result,
            commit_status=commit.commit_status,
        )
        commit = _with_commit_substep(commit, name="trace", status="committed")
        if commit.commit_status == "failed":
            return None
        logger.info(
            "AI trace {} generated {} reply for session {} with source={} "
            "model={} memories={} tool_observations={} entry_kind={} "
            "entry_trigger={}",
            trace_id,
            request.runtime_mode,
            identity.session_id,
            response.source_id,
            response.model_name,
            len(inputs.recalled_memories),
            len(execution.skill_runtime.turns),
            trace.kind,
            trace.trigger,
        )
        return replace(commit, trace=trace_outcome.trace)

    def evaluate_policy(
        self,
        *,
        request: Any,
        wake_context: "WakeContext",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimePolicyOutcome:
        """Evaluate deterministic runtime policy for one turn."""

        return self.policy_stage.evaluate(
            request=request,
            wake_context=wake_context,
            current_time=current_time,
            session_runtime=session_runtime,
        )

    async def apply_observation_side_effects(
        self,
        *,
        request: Any,
        current_time: "datetime",
    ) -> None:
        """Apply live observation writes outside read-oriented context assembly."""

        await self.observation_stage.apply(
            request=request,
            current_time=current_time,
        )

    async def assemble_context(
        self,
        *,
        request: Any,
        current_time: "datetime",
    ) -> RuntimeContextBundle:
        """Gather prompt-facing context materials for one turn."""

        return await self.context_stage.assemble(
            request=request,
            current_time=current_time,
        )

    async def plan_turn(
        self,
        *,
        trace_id: str,
        request: Any,
        inputs: Any,
        social_decision: Any,
        current_time: "datetime",
    ) -> RuntimeTurnPlan | None:
        """Build the runtime-owned plan consumed by execution."""

        return await self.planning_stage.plan(
            trace_id=trace_id,
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
        )

    async def execute_turn(
        self,
        *,
        turn_context: Any,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome:
        """Execute one direct or tool-capable turn."""

        return await self.execution_stage.execute(
            turn_context=turn_context,
            plan=plan,
        )

    async def commit_turn(  # noqa: PLR0913
        self,
        *,
        request: Any,
        inputs: Any,
        social_decision: Any,
        plan: RuntimeTurnPlan,
        generation: RuntimeExecutionOutcome,
        trace_id: str,
        hard_decision: "RuntimeHardRuleDecision",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimeCommitResult:
        """Persist one generated turn through the commit stage."""

        return await self.commit_stage.commit(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            plan=plan,
            generation=generation,
            trace_id=trace_id,
            hard_decision=hard_decision,
            current_time=current_time,
            session_runtime=session_runtime,
        )

    def project_trace(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        request: Any,
        strategy_decision: "RuntimeHardRuleDecision",
        turn_result: "AgentTurnResult | None",
        delivery_result: "DeliveryOutcome | None" = None,
        commit_status: str | None = None,
    ) -> RuntimeTraceOutcome:
        """Project one terminal generated or non-generated outcome."""

        return self.trace_stage.project(
            trace_id=trace_id,
            request=request,
            strategy_decision=strategy_decision,
            turn_result=turn_result,
            delivery_result=delivery_result,
            commit_status=commit_status,
        )

    @staticmethod
    def _build_fallback_wake_context(request: Any) -> "WakeContext":
        from apeiria.app.ai.pipeline.reply_strategy_steps import (
            build_fallback_wake_context,
        )

        return build_fallback_wake_context(request)


def _delivery_target_for_request(request: Any) -> DeliveryTarget:
    if request.runtime_mode == "future_task":
        return DeliveryTarget(
            session_id=request.identity.session_id,
            delivery_channel="future_task",
        )
    return DeliveryTarget(
        session_id=request.identity.session_id,
        reply_to_message_id=request.source_message_id,
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
    "DefaultRuntimeCommitStage",
    "DefaultRuntimeContextStage",
    "DefaultRuntimeExecutionStage",
    "DefaultRuntimeObservationStage",
    "DefaultRuntimePlanningStage",
    "DefaultRuntimePolicyStage",
    "DefaultRuntimeTraceStage",
]
