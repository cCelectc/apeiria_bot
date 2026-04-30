"""Session runtime turn engine with explicit stage boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from .context import DeliveryTarget, RuntimeTurnSource
from .context_adapter import build_turn_context
from .hard_rules import decide_runtime_hard_rule, map_legacy_skip_to_runtime_decision
from .stages import (
    RuntimeCommitResult,
    RuntimeContextBundle,
    RuntimeExecutionOutcome,
    RuntimePolicyOutcome,
    RuntimeTraceOutcome,
    RuntimeTurnPlan,
)
from .tools import ToolExposurePlan
from .trace import project_turn_trace

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.pipeline.generation_steps import ReplyGeneration
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.session_runtime.strategy import RuntimeHardRuleDecision


@dataclass(frozen=True, slots=True)
class AISessionTurnEngine:
    """Coordinate one normalized AI turn through named runtime stages."""

    gather_reply_inputs: "Callable[..., Awaitable[Any]]"
    decide_whether_to_speak: "Callable[..., Awaitable[Any]]"
    prepare_generation: "Callable[..., Awaitable[Any]]"
    generate_reply: "Callable[..., Awaitable[Any]]"
    persist_reply: "Callable[..., Awaitable[None]]"
    reply_strategy_service: Any
    apply_observation_effects: "Callable[..., Awaitable[None]] | None" = None
    trace_observer: "Callable[[RuntimeTraceOutcome], None] | None" = None

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
        social_decision = await self.decide_whether_to_speak(
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
        execution = await self.execute_turn(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            plan=plan,
            current_time=current_time,
            trace_id=trace_id,
            turn_context=turn_context,
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
                trace_id=trace_id,
                request=request,
                strategy_decision=hard_decision,
                turn_result=execution.turn_result,
                delivery_result=execution.delivery_result,
            )
            return None

        await self.commit_turn(
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
            delivery_result=execution.delivery_result,
        )
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
        return RuntimeCommitResult(
            stage="commit",
            reply_text=response.content.strip(),
            delivery_result=execution.delivery_result,
            trace=trace_outcome.trace,
        )

    def evaluate_policy(
        self,
        *,
        request: Any,
        wake_context: "WakeContext",
        current_time: "datetime",
        session_runtime: Any | None,
    ) -> RuntimePolicyOutcome:
        """Evaluate deterministic runtime policy for one turn."""

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

    async def apply_observation_side_effects(
        self,
        *,
        request: Any,
        current_time: "datetime",
    ) -> None:
        """Apply live observation writes outside read-oriented context assembly."""

        if self.apply_observation_effects is None:
            return
        await self.apply_observation_effects(
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

        inputs = await self.gather_reply_inputs(request, current_time)
        return RuntimeContextBundle(stage="context", inputs=inputs)

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

        prep = await self.prepare_generation(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            current_time=current_time,
            trace_id=trace_id,
        )
        if prep is None:
            return None

        from apeiria.app.ai.pipeline.generation_steps import (
            build_initial_reply_prompt_diagnostics,
            build_initial_reply_prompt_messages,
            select_pipeline_fallback_models,
        )

        return RuntimeTurnPlan(
            stage="planning",
            selected=prep.selected,
            fallback_models=await select_pipeline_fallback_models(prep.selected),
            skill_runtime=prep.skill_runtime,
            skill_activation=prep.skill_activation,
            pre_tool_task_class=prep.pre_tool_task_class,
            prompt_messages=build_initial_reply_prompt_messages(
                request=request,
                inputs=inputs,
                social_decision=social_decision,
                prep=prep,
            ),
            prompt_diagnostics=build_initial_reply_prompt_diagnostics(
                request=request,
                inputs=inputs,
                social_decision=social_decision,
                prep=prep,
            ),
            tool_exposure_plan=_tool_exposure_plan_from_preparation(prep),
        )

    async def execute_turn(  # noqa: PLR0913
        self,
        *,
        request: Any,
        inputs: Any,
        social_decision: Any,
        plan: RuntimeTurnPlan,
        current_time: "datetime",
        trace_id: str,
        turn_context: Any,
    ) -> RuntimeExecutionOutcome:
        """Execute one direct or tool-capable turn."""

        generation: "ReplyGeneration" = await self.generate_reply(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=plan,
            current_time=current_time,
            trace_id=trace_id,
            turn_context=turn_context,
            turn_plan=plan,
        )
        return RuntimeExecutionOutcome(
            stage="execution",
            response=generation.response,
            skill_runtime=generation.skill_runtime,
            post_tool_task_class=generation.post_tool_task_class,
            delivery_result=generation.delivery_result,
            turn_result=generation.turn_result,
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
    ) -> None:
        """Persist one generated turn through the commit stage."""

        await self.persist_reply(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=plan,
            gen=generation,
            trace_id=trace_id,
        )
        if generation.delivery_result is None or generation.delivery_result.delivered:
            self.reply_strategy_service.notify_replied(request.identity.session_id)
            if session_runtime is not None and hard_decision.reason_codes == (
                "ambient_candidate",
            ):
                session_runtime.record_ambient_reply(now=current_time)

    def project_trace(
        self,
        *,
        trace_id: str,
        request: Any,
        strategy_decision: "RuntimeHardRuleDecision",
        turn_result: "AgentTurnResult | None",
        delivery_result: "DeliveryOutcome | None" = None,
    ) -> RuntimeTraceOutcome:
        """Project one terminal generated or non-generated outcome."""

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
        return outcome

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


def _tool_exposure_plan_from_preparation(prep: Any) -> ToolExposurePlan:
    return ToolExposurePlan(
        selected_tools=prep.skill_runtime.available_tools,
        diagnostics={
            "selected_tool_count": len(prep.skill_runtime.available_tools),
            "source": "tool_gateway_prepare",
        },
    )


def _should_serialize_in_engine(session_runtime: Any | None) -> bool:
    if session_runtime is None or not hasattr(session_runtime, "run_serialized"):
        return False
    return not bool(getattr(session_runtime, "current_turn_owns_lock", False))


__all__ = ["AISessionTurnEngine"]
