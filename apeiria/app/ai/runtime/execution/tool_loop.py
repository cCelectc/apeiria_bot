"""Runtime-owned model/tool loop execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from nonebot.log import logger

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallOptions,
    AIModelCallRequirements,
    AIModelCapabilityPlanningError,
)
from apeiria.ai.tools.function_calling import (
    build_intents_from_tool_calls,
    function_name_to_tool_name,
)
from apeiria.ai.tools.loop.history import repair_tool_message_history
from apeiria.ai.tools.loop.projection import (
    ToolResult,
    completed_observations,
    project_tool_results,
    summarize_arguments,
)
from apeiria.ai.tools.loop.prompt_budget import (
    DEFAULT_OBSERVATION_CHAR_LIMIT,
    build_prompt_safe_observation,
    is_context_pressure_error,
    recover_prompt_budget_messages,
)
from apeiria.ai.tools.loop.state import ToolLoopState
from apeiria.ai.tools.models import (
    AIToolExecutionRequest,
    AIToolObservationResult,
    AIToolPolicy,
)
from apeiria.ai.tools.policy import summarize_tool_policy
from apeiria.ai.turn_records import (
    ModelAttempt,
    ToolAttempt,
    is_empty_model_response,
)
from apeiria.app.ai.agent_turn.attempts import (
    build_capability_failure_attempt,
    build_empty_response_attempt,
    build_exception_failure_attempt,
    build_success_attempt,
)
from apeiria.app.ai.usage_recording import (
    AIModelUsageRecordContext,
    record_model_usage_safely,
)
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelGenerateResponse,
        AIModelToolDefinition,
    )
    from apeiria.ai.tools.models import AIToolIntent, AIToolTurnCreateInput
    from apeiria.ai.tools.service import AIToolService
    from apeiria.ai.turn_records import ToolAttemptStatus

MAX_TOOL_ROUNDS = 3
DEFAULT_REPEATED_TOOL_THRESHOLD = 3
MAX_ROUNDS_FINALIZATION_PROMPT = "\n".join(
    (
        "The tool loop reached its maximum number of rounds.",
        "Do not call any tools. Use the available tool observations and produce "
        "the best final answer you can.",
    )
)


@dataclass(frozen=True)
class RuntimeToolLoopInput:
    """Inputs needed to run the runtime-owned model/tool loop."""

    trace_id: str | None
    session_id: str
    source_message_id: str | None
    runtime_mode: str
    message_text: str
    current_time: "datetime"
    selected: "AISelectedModel"
    fallback_models: tuple["AISelectedModel", ...]
    messages: tuple[AIModelMessage, ...]
    tools: tuple["AIModelToolDefinition", ...]
    tool_policy: AIToolPolicy
    executable_tool_names: frozenset[str] | None
    recalled_memory_ids: tuple[str, ...]
    recalled_memory_contents: tuple[str, ...]
    relationship_context: str | None
    actor_id: str | None = None
    chat_scope_type: str | None = None
    chat_scope_id: str | None = None
    reply_audience: str | None = None
    provider_name_map: Mapping[str, str] | None = None
    execution_timeout_seconds: float | None = None
    tool_mode: str = "allow"
    reasoning_options: AIModelCallOptions | None = None


@dataclass(frozen=True)
class RuntimeToolLoopResult:
    """Aggregated runtime tool-loop output consumed by execution/commit."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]
    tool_results: tuple[ToolResult, ...] = ()
    model_attempts: tuple[ModelAttempt, ...] = ()
    tool_attempts: tuple[ToolAttempt, ...] = ()
    available_tools: tuple["AIModelToolDefinition", ...] = field(default_factory=tuple)
    final_response: "AIModelGenerateResponse | None" = None
    tool_turns: tuple["AIToolTurnCreateInput", ...] = ()
    tool_messages: tuple[AIModelMessage, ...] = ()
    finish_reason: str = "not_started"
    selected: "AISelectedModel | None" = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


class RuntimeToolLoopRunner:
    """Run model/tool loop rounds for a planned runtime turn."""

    def __init__(
        self,
        *,
        model_invoker: Any | None = None,
        tool_service: "AIToolService | None" = None,
        usage_recorder: Any | None = None,
    ) -> None:
        if model_invoker is None:
            model_invoker = ai_wiring.model.invoker
        if tool_service is None:
            tool_service = ai_wiring.tool_service
        if usage_recorder is None:
            from apeiria.app.ai.usage_recording import (
                ai_model_usage_recorder as default_usage_recorder,
            )

            usage_recorder = default_usage_recorder
        self._model_invoker = model_invoker
        self._tool_service = tool_service
        self._usage_recorder = usage_recorder

    def prepare(
        self,
        *,
        policy: AIToolPolicy,
        allowed_tools: tuple[Any, ...],
        available_tools: tuple["AIModelToolDefinition", ...],
    ) -> RuntimeToolLoopResult:
        """Build pre-loop tool policy text and provider tool schema."""

        return RuntimeToolLoopResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                policy,
            ),
            result_lines=(),
            turns=(),
            available_tools=available_tools,
            diagnostics={"selected_tool_count": len(allowed_tools)},
        )

    async def run(  # noqa: PLR0915
        self,
        loop_input: RuntimeToolLoopInput,
        *,
        max_rounds: int = MAX_TOOL_ROUNDS,
        observation_char_limit: int = DEFAULT_OBSERVATION_CHAR_LIMIT,
        repeated_tool_threshold: int = DEFAULT_REPEATED_TOOL_THRESHOLD,
        tool_calling_requirement: Literal["required", "optional", "none"] = "required",
    ) -> RuntimeToolLoopResult:
        all_result_lines: list[str] = []
        all_turns: list[AIToolTurnCreateInput] = []
        all_tool_results: list[ToolResult] = []
        all_model_attempts: list[ModelAttempt] = []
        all_tool_attempts: list[ToolAttempt] = []
        tool_message_history: list[AIModelMessage] = []
        final_response: AIModelGenerateResponse | None = None
        finish_reason = "not_started"
        current_selected = loop_input.selected
        loop_state = ToolLoopState()

        for _ in range(max_rounds):
            round_idx = loop_state.next_round()
            current_messages = repair_tool_message_history(
                (*loop_input.messages, *tool_message_history),
                loop_state=loop_state,
            )

            model_result = await self._generate_tool_loop_model(
                loop_input=loop_input,
                selected=current_selected,
                messages=current_messages,
                tools=loop_input.tools,
                fallback_models=_dedupe_fallbacks(
                    current_selected,
                    loop_input.fallback_models,
                ),
                tool_calling_requirement=tool_calling_requirement,
                loop_state=loop_state,
                response_source="tool_loop",
                allow_context_recovery=True,
                reasoning_options=loop_input.reasoning_options,
            )
            all_model_attempts.extend(model_result.attempts)
            response = model_result.response
            if response is None:
                finish_reason = model_result.finish_reason
                break
            current_selected = model_result.selected

            final_response = response
            if not response.tool_calls:
                finish_reason = "final_response"
                break

            tool_message_history.append(
                AIModelMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            intents = build_intents_from_tool_calls(
                response.tool_calls,
                provider_name_map=(
                    dict(loop_input.provider_name_map)
                    if loop_input.provider_name_map is not None
                    else None
                ),
            )
            observations = await self._execute_intents_with_policy(loop_input, intents)
            tool_results = project_tool_results(response.tool_calls, observations)
            executed_observations = completed_observations(observations)
            all_tool_results.extend(tool_results)
            all_turns.extend(self._tool_service.build_tool_turns(executed_observations))

            obs_by_index = dict(enumerate(observations))
            round_statuses: list[ToolAttemptStatus] = []
            for index, tool_call in enumerate(response.tool_calls):
                obs = obs_by_index.get(index)
                tool_name = (
                    intents[index].tool_name
                    if index < len(intents)
                    else function_name_to_tool_name(tool_call.name)
                )
                repetition_count = loop_state.next_tool_repetition_count(tool_name)
                repeated = repetition_count >= repeated_tool_threshold
                observation_text = (
                    obs.summary
                    if obs is not None
                    else f"- [{tool_name}] skipped: execution limit"
                )
                safe_observation = build_prompt_safe_observation(
                    observation_text,
                    char_limit=observation_char_limit,
                )
                diagnostic = (
                    f"repeated tool call count={repetition_count}" if repeated else None
                )
                status: ToolAttemptStatus = obs.status if obs is not None else "skipped"
                round_statuses.append(status)
                all_tool_attempts.append(
                    ToolAttempt(
                        tool_call_id=tool_call.tool_call_id,
                        tool_name=tool_name,
                        status=status,
                        arguments_summary=summarize_arguments(tool_call.arguments),
                        observation=safe_observation,
                        repetition_count=repetition_count,
                        repeated=repeated,
                        diagnostic=diagnostic,
                        native_observation=obs,
                    )
                )
                all_result_lines.append(safe_observation.content)
                tool_message_history.append(
                    AIModelMessage(
                        role="tool",
                        content=safe_observation.content,
                        tool_call_id=tool_call.tool_call_id,
                    )
                )

            loop_state.record_tool_round(round_statuses)
            logger.debug(
                "Tool loop round {} completed: {} tool calls, {} observations",
                round_idx,
                len(response.tool_calls),
                len(observations),
            )
        else:
            if final_response is not None and final_response.tool_calls:
                finish_reason = "max_rounds_reached"
                finalization = await self._finalize_after_max_rounds(
                    selected=current_selected,
                    messages=(*loop_input.messages, *tool_message_history),
                    loop_input=loop_input,
                    fallback_models=_dedupe_fallbacks(
                        current_selected,
                        loop_input.fallback_models,
                    ),
                    tool_calling_requirement="none",
                    loop_state=loop_state,
                )
                all_model_attempts.extend(finalization.attempts)
                if (
                    finalization.response is not None
                    and finalization.response.content.strip()
                ):
                    final_response = finalization.response
                    current_selected = finalization.selected

        turns = tuple(all_turns)
        return RuntimeToolLoopResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                loop_input.tool_policy,
            ),
            result_lines=tuple(all_result_lines),
            turns=turns,
            tool_results=tuple(all_tool_results),
            model_attempts=tuple(all_model_attempts),
            tool_attempts=tuple(all_tool_attempts),
            available_tools=(),
            final_response=final_response,
            tool_turns=turns,
            tool_messages=tuple(tool_message_history),
            finish_reason=finish_reason,
            selected=current_selected,
            diagnostics=loop_state.metadata(),
        )

    @staticmethod
    def _build_execution_request(
        loop_input: RuntimeToolLoopInput,
    ) -> AIToolExecutionRequest:
        return AIToolExecutionRequest(
            session_id=loop_input.session_id,
            source_message_id=loop_input.source_message_id,
            trace_id=loop_input.trace_id,
            message_text=loop_input.message_text,
            policy=loop_input.tool_policy,
            recalled_memory_ids=loop_input.recalled_memory_ids,
            recalled_memory_contents=loop_input.recalled_memory_contents,
            relationship_context=loop_input.relationship_context,
            execution_timeout_seconds=loop_input.execution_timeout_seconds,
            actor_id=loop_input.actor_id,
            chat_scope_type=loop_input.chat_scope_type,
            chat_scope_id=loop_input.chat_scope_id,
            reply_audience=loop_input.reply_audience,
        )

    async def _execute_intents_with_policy(
        self,
        loop_input: RuntimeToolLoopInput,
        intents: list["AIToolIntent"],
    ) -> list["AIToolObservationResult | None"]:
        allowed_names = {
            tool.name
            for tool in self._tool_service.list_allowed_tools(loop_input.tool_policy)
        }
        if loop_input.tool_mode == "avoid":
            allowed_names = set()

        observations: list[AIToolObservationResult | None] = [None] * len(intents)
        allowed_intents: list[AIToolIntent] = []
        allowed_positions: list[int] = []
        for index, intent in enumerate(intents):
            exposure_decision = self._evaluate_execution_exposure(loop_input, intent)
            if exposure_decision is not None:
                observations[index] = exposure_decision
                continue
            if intent.tool_name not in allowed_names:
                reason = "denied by policy"
                observations[index] = AIToolObservationResult(
                    tool_name=intent.tool_name,
                    summary=f"- [{intent.tool_name}] {reason}",
                    input_payload=intent.input_payload,
                    output_payload={
                        "error": "denied_by_policy",
                        "trace_id": loop_input.trace_id,
                    },
                    status="denied",
                    reason=reason,
                    call_id=intent.call_id,
                )
                continue
            allowed_intents.append(intent)
            allowed_positions.append(index)

        if allowed_intents:
            executed = await self._tool_service.execute_tool_intents(
                request=self._build_execution_request(loop_input),
                intents=allowed_intents,
            )
            for position, observation in zip(allowed_positions, executed, strict=False):
                observations[position] = observation

        return observations

    def _evaluate_execution_exposure(
        self,
        loop_input: RuntimeToolLoopInput,
        intent: "AIToolIntent",
    ) -> "AIToolObservationResult | None":
        if (
            loop_input.executable_tool_names is not None
            and intent.tool_name not in loop_input.executable_tool_names
        ):
            return self._build_not_exposed_observation(loop_input, intent)
        return None

    @staticmethod
    def _build_not_exposed_observation(
        loop_input: RuntimeToolLoopInput,
        intent: "AIToolIntent",
    ) -> AIToolObservationResult:
        return AIToolObservationResult(
            tool_name=intent.tool_name,
            summary=f"- [{intent.tool_name}] not exposed for this turn",
            input_payload=intent.input_payload,
            output_payload={
                "error": "not_exposed_for_turn",
                "trace_id": loop_input.trace_id,
            },
            status="denied",
            reason="not exposed for this turn",
            call_id=intent.call_id,
        )

    async def _generate_tool_loop_model(  # noqa: C901, PLR0913
        self,
        *,
        loop_input: RuntimeToolLoopInput,
        selected: "AISelectedModel",
        messages: tuple[AIModelMessage, ...],
        tools: tuple["AIModelToolDefinition", ...],
        fallback_models: tuple["AISelectedModel", ...],
        tool_calling_requirement: Literal["required", "optional", "none"],
        loop_state: ToolLoopState,
        response_source: str,
        allow_context_recovery: bool,
        reasoning_options: AIModelCallOptions | None = None,
    ) -> "_ToolLoopModelResult":
        attempts: list[ModelAttempt] = []
        last_finish_reason = "model_error"
        messages_for_call = messages
        recovered_messages_active = False

        for candidate in (selected, *fallback_models):
            while True:
                try:
                    response = await self._model_invoker.generate_text(
                        selected=candidate,
                        messages=messages_for_call,
                        tools=tools,
                        requirements=AIModelCallRequirements(
                            tool_calling=(
                                tool_calling_requirement if tools else "none"
                            ),
                        ),
                        options=reasoning_options,
                    )
                except AIModelCapabilityPlanningError as exc:
                    attempts.append(
                        build_capability_failure_attempt(
                            attempt_index=loop_state.next_model_attempt_index(),
                            selected=candidate,
                            response_source=response_source,
                            exc=exc,
                        )
                    )
                    last_finish_reason = "capability_unavailable"
                    break
                except Exception as exc:  # noqa: BLE001
                    attempt_index = loop_state.next_model_attempt_index()
                    diagnostic = str(exc)
                    is_context_pressure = is_context_pressure_error(diagnostic)
                    reason = "context_pressure" if is_context_pressure else None
                    attempts.append(
                        build_exception_failure_attempt(
                            attempt_index=attempt_index,
                            selected=candidate,
                            response_source=response_source,
                            exc=exc,
                            planned_feature=_planned_feature_for_tool_loop(
                                tools=tools,
                                tool_calling_requirement=tool_calling_requirement,
                                messages=messages_for_call,
                            ),
                            classify_capability=not is_context_pressure,
                            reason=reason,
                        )
                    )
                    last_finish_reason = attempts[-1].reason or "model_error"
                    if (
                        is_context_pressure
                        and allow_context_recovery
                        and loop_state.can_attempt_context_recovery()
                    ):
                        recovered, compacted = recover_prompt_budget_messages(
                            messages_for_call
                        )
                        loop_state.context_recovery_compacted_messages += compacted
                        if compacted:
                            loop_state.model_retry_count += 1
                            messages_for_call = recovered
                            recovered_messages_active = True
                            continue
                        loop_state.context_recovery_failed = True
                    elif recovered_messages_active:
                        loop_state.context_recovery_failed = True
                    break

                if is_empty_model_response(response):
                    attempt_index = loop_state.next_model_attempt_index()
                    _record_tool_loop_usage(
                        recorder=self._usage_recorder,
                        loop_input=loop_input,
                        selected=candidate,
                        response=response,
                        response_source=response_source,
                        attempt_index=attempt_index,
                        status="empty_response",
                    )
                    attempts.append(
                        build_empty_response_attempt(
                            attempt_index=attempt_index,
                            selected=candidate,
                            response_source=response_source,
                        )
                    )
                    last_finish_reason = "empty_response"
                    if recovered_messages_active:
                        loop_state.context_recovery_failed = True
                    break

                attempt_index = loop_state.next_model_attempt_index()
                _record_tool_loop_usage(
                    recorder=self._usage_recorder,
                    loop_input=loop_input,
                    selected=candidate,
                    response=response,
                    response_source=response_source,
                    attempt_index=attempt_index,
                    status="success",
                )
                attempts.append(
                    build_success_attempt(
                        attempt_index=attempt_index,
                        selected=candidate,
                        response_source=response_source,
                        response=response,
                        reasoning_options=reasoning_options,
                    )
                )
                _record_response_degradations(response, loop_state)
                if recovered_messages_active:
                    loop_state.context_recovery_succeeded = True
                return _ToolLoopModelResult(
                    response=response,
                    selected=candidate,
                    attempts=tuple(attempts),
                    finish_reason=f"{response_source}_model_completed",
                )
            messages_for_call = messages
            recovered_messages_active = False

        return _ToolLoopModelResult(
            response=None,
            selected=selected,
            attempts=tuple(attempts),
            finish_reason=last_finish_reason,
        )

    async def _finalize_after_max_rounds(  # noqa: PLR0913
        self,
        *,
        loop_input: RuntimeToolLoopInput,
        selected: "AISelectedModel",
        messages: tuple[AIModelMessage, ...],
        fallback_models: tuple["AISelectedModel", ...],
        tool_calling_requirement: Literal["required", "optional", "none"],
        loop_state: ToolLoopState,
    ) -> "_ToolLoopModelResult":
        loop_state.finalization_attempted = True
        finalization_prompt = AIModelMessage(
            role="user",
            content=MAX_ROUNDS_FINALIZATION_PROMPT,
        )
        finalization_messages = repair_tool_message_history(
            (*messages, finalization_prompt),
            loop_state=loop_state,
        )
        result = await self._generate_tool_loop_model(
            loop_input=loop_input,
            selected=selected,
            messages=finalization_messages,
            tools=(),
            fallback_models=fallback_models,
            tool_calling_requirement=tool_calling_requirement,
            loop_state=loop_state,
            response_source="tool_loop_finalization",
            allow_context_recovery=False,
            reasoning_options=None,
        )
        response = result.response
        if response is None:
            loop_state.finalization_error = result.finish_reason
            return result
        loop_state.finalization_ignored_tool_calls = len(response.tool_calls)
        if response.content.strip():
            loop_state.finalization_succeeded = True
        else:
            loop_state.finalization_error = "empty_response"
        return result


@dataclass(frozen=True)
class _ToolLoopModelResult:
    response: "AIModelGenerateResponse | None"
    selected: "AISelectedModel"
    attempts: tuple[ModelAttempt, ...]
    finish_reason: str


def _dedupe_fallbacks(
    selected: "AISelectedModel",
    fallback_models: tuple["AISelectedModel", ...],
) -> tuple["AISelectedModel", ...]:
    selected_key = (selected.source.source_id, selected.resolved_model_name)
    seen = {selected_key}
    deduped: list[AISelectedModel] = []
    for model in fallback_models:
        key = (model.source.source_id, model.resolved_model_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(model)
    return tuple(deduped)


def _record_response_degradations(
    response: "AIModelGenerateResponse",
    loop_state: ToolLoopState,
) -> None:
    provider_data = response.provider_data or {}
    degradations = provider_data.get("apeiria_degradations")
    if not isinstance(degradations, list):
        return
    for item in degradations:
        if isinstance(item, dict):
            loop_state.capability_degradations.append(dict(item))


def _record_tool_loop_usage(  # noqa: PLR0913
    *,
    recorder: Any | None,
    loop_input: RuntimeToolLoopInput,
    selected: "AISelectedModel",
    response: "AIModelGenerateResponse",
    response_source: str,
    attempt_index: int,
    status: str,
) -> None:
    record_model_usage_safely(
        recorder=recorder,
        context=AIModelUsageRecordContext(
            trace_id=loop_input.trace_id,
            session_id=loop_input.session_id,
            runtime_mode=loop_input.runtime_mode,
            response_source=response_source,
            selected=selected,
            operation="chat_generation",
            attempt_index=attempt_index,
            status=status,
        ),
        response=response,
    )


def _planned_feature_for_tool_loop(
    *,
    tools: tuple["AIModelToolDefinition", ...],
    tool_calling_requirement: Literal["required", "optional", "none"],
    messages: tuple[AIModelMessage, ...],
) -> str:
    if tools and tool_calling_requirement != "none":
        return "tool_calling"
    for message in messages:
        for part in getattr(message, "parts", ()):
            kind = getattr(part, "kind", None)
            if kind in {"image", "audio", "file"}:
                return "modality"
    return "unknown"


runtime_tool_loop_runner = RuntimeToolLoopRunner()

__all__ = [
    "DEFAULT_OBSERVATION_CHAR_LIMIT",
    "DEFAULT_REPEATED_TOOL_THRESHOLD",
    "MAX_TOOL_ROUNDS",
    "RuntimeToolLoopInput",
    "RuntimeToolLoopResult",
    "RuntimeToolLoopRunner",
    "runtime_tool_loop_runner",
]
