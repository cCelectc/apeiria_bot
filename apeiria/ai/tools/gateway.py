"""AI-internal tool gateway for reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from nonebot.log import logger

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallRequirements,
    AIModelCapabilityPlanningError,
)
from apeiria.ai.model.runtime.capability_sources import classify_capability_mismatch
from apeiria.ai.tools.function_calling import (
    build_function_tools,
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
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolPolicy,
)
from apeiria.ai.tools.policy import summarize_tool_policy
from apeiria.ai.turn_records import (
    ModelAttempt,
    ToolAttempt,
    is_empty_model_response,
    model_ref,
    sanitize_model_diagnostic,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory.models import AIMemoryDefinition
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import (
        AIModelGenerateResponse,
        AIModelToolCall,
        AIModelToolDefinition,
    )
    from apeiria.ai.tools.models import (
        AIToolIntent,
        AIToolTurnCreateInput,
    )
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
class ToolGatewayRequest:
    """Inputs needed to run tools for a single reply turn."""

    session_id: str
    source_message_id: str | None
    trace_id: str | None
    message_text: str
    policy: AIToolPolicy
    recalled_memories: tuple["AIMemoryDefinition", ...]
    relationship_context: str | None
    current_time: "datetime"
    runtime_mode: str = "message"
    tool_mode: str = "allow"
    execution_timeout_seconds: float | None = None


@dataclass(frozen=True)
class ToolGatewayResult:
    """Aggregated tool runtime output consumed by reply orchestration."""

    policy_text: str
    result_lines: tuple[str, ...]
    turns: tuple["AIToolTurnCreateInput", ...]
    tool_results: tuple[ToolResult, ...] = ()
    model_attempts: tuple[ModelAttempt, ...] = ()
    tool_attempts: tuple[ToolAttempt, ...] = ()
    available_tools: tuple["AIModelToolDefinition", ...] = field(default_factory=tuple)
    final_response: "AIModelGenerateResponse | None" = None
    tool_messages: tuple[AIModelMessage, ...] = ()
    loop_finish_reason: str = "not_started"
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolGateway:
    """AI-internal tool execution gateway."""

    def __init__(
        self,
        *,
        model_gateway: Any | None = None,
        tool_service: Any | None = None,
    ) -> None:
        if model_gateway is None:
            from apeiria.ai.model import model_gateway as default_model_gateway

            model_gateway = default_model_gateway
        if tool_service is None:
            from apeiria.ai.tools.service import ai_tool_service

            tool_service = ai_tool_service
        self._model_gateway = model_gateway
        self._tool_service = tool_service

    async def prepare(
        self,
        request: ToolGatewayRequest,
    ) -> ToolGatewayResult:
        allowed_tools = self._tool_service.list_allowed_tools(request.policy)
        if request.tool_mode == "avoid":
            allowed_tools = []
        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=(),
            turns=(),
            available_tools=build_function_tools(
                allowed_tools,
                current_time=request.current_time,
            ),
        )

    async def execute_tool_calls(
        self,
        request: ToolGatewayRequest,
        *,
        tool_calls: tuple["AIModelToolCall", ...],
    ) -> ToolGatewayResult:
        intents = build_intents_from_tool_calls(tool_calls)
        observations = await self._execute_intents_with_policy(request, intents)
        tool_results = project_tool_results(tool_calls, observations)
        executed_observations = completed_observations(observations)
        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(
                obs.summary if obs is not None else "- [tool] skipped: execution limit"
                for obs in observations
            ),
            turns=tuple(self._tool_service.build_tool_turns(executed_observations)),
            tool_results=tool_results,
            available_tools=(),
        )

    async def run_tool_loop(  # noqa: PLR0913, PLR0915
        self,
        request: ToolGatewayRequest,
        *,
        messages: list[AIModelMessage],
        tools: tuple["AIModelToolDefinition", ...],
        selected: "AISelectedModel",
        max_rounds: int = MAX_TOOL_ROUNDS,
        observation_char_limit: int = DEFAULT_OBSERVATION_CHAR_LIMIT,
        repeated_tool_threshold: int = DEFAULT_REPEATED_TOOL_THRESHOLD,
        fallback_models: tuple["AISelectedModel", ...] = (),
        tool_calling_requirement: Literal["required", "optional", "none"] = "required",
    ) -> ToolGatewayResult:
        all_result_lines: list[str] = []
        all_turns: list[AIToolTurnCreateInput] = []
        all_tool_results: list[ToolResult] = []
        all_model_attempts: list[ModelAttempt] = []
        all_tool_attempts: list[ToolAttempt] = []
        tool_message_history: list[AIModelMessage] = []
        final_response: AIModelGenerateResponse | None = None
        loop_finish_reason = "not_started"
        current_selected = selected
        loop_state = ToolLoopState()

        for _ in range(max_rounds):
            round_idx = loop_state.next_round()
            current_messages = repair_tool_message_history(
                (*messages, *tool_message_history),
                loop_state=loop_state,
            )

            model_result = await self._generate_tool_loop_model(
                selected=current_selected,
                messages=current_messages,
                tools=tools,
                fallback_models=_dedupe_fallbacks(
                    current_selected,
                    fallback_models,
                ),
                tool_calling_requirement=tool_calling_requirement,
                loop_state=loop_state,
                response_source="tool_loop",
                allow_context_recovery=True,
            )
            all_model_attempts.extend(model_result.attempts)
            response = model_result.response
            if response is None:
                loop_finish_reason = model_result.finish_reason
                break
            current_selected = model_result.selected

            final_response = response
            if not response.tool_calls:
                loop_finish_reason = "final_response"
                break

            tool_message_history.append(
                AIModelMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
            )

            intents = build_intents_from_tool_calls(response.tool_calls)
            observations = await self._execute_intents_with_policy(request, intents)
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
                loop_finish_reason = "max_rounds_reached"
                finalization = await self._finalize_after_max_rounds(
                    selected=current_selected,
                    messages=(*messages, *tool_message_history),
                    fallback_models=_dedupe_fallbacks(
                        current_selected,
                        fallback_models,
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

        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(all_result_lines),
            turns=tuple(all_turns),
            tool_results=tuple(all_tool_results),
            model_attempts=tuple(all_model_attempts),
            tool_attempts=tuple(all_tool_attempts),
            available_tools=(),
            final_response=final_response,
            tool_messages=tuple(tool_message_history),
            loop_finish_reason=loop_finish_reason,
            metadata=loop_state.metadata(),
        )

    @staticmethod
    def _build_observation_request(
        request: ToolGatewayRequest,
    ) -> AIToolObservationRequest:
        return AIToolObservationRequest(
            session_id=request.session_id,
            source_message_id=request.source_message_id,
            trace_id=request.trace_id,
            message_text=request.message_text,
            policy=request.policy,
            recalled_memory_ids=tuple(m.memory_id for m in request.recalled_memories),
            recalled_memory_contents=tuple(
                m.content for m in request.recalled_memories
            ),
            relationship_context=request.relationship_context,
            execution_timeout_seconds=request.execution_timeout_seconds,
        )

    async def _execute_intents_with_policy(
        self,
        request: ToolGatewayRequest,
        intents: list["AIToolIntent"],
    ) -> list["AIToolObservationResult | None"]:
        allowed_names = {
            tool.name for tool in self._tool_service.list_allowed_tools(request.policy)
        }
        if request.tool_mode == "avoid":
            allowed_names = set()

        observations: list[AIToolObservationResult | None] = [None] * len(intents)
        allowed_intents: list[AIToolIntent] = []
        allowed_positions: list[int] = []
        for index, intent in enumerate(intents):
            if intent.tool_name not in allowed_names:
                observations[index] = AIToolObservationResult(
                    tool_name=intent.tool_name,
                    summary=f"- [{intent.tool_name}] denied by policy",
                    input_payload=intent.input_payload,
                    output_payload={
                        "error": "denied_by_policy",
                        "trace_id": request.trace_id,
                    },
                    status="error",
                )
                continue
            allowed_intents.append(intent)
            allowed_positions.append(index)

        if allowed_intents:
            executed = await self._tool_service.execute_tool_intents(
                request=self._build_observation_request(request),
                intents=allowed_intents,
            )
            for position, observation in zip(allowed_positions, executed, strict=False):
                observations[position] = observation

        return observations

    async def _generate_tool_loop_model(  # noqa: C901, PLR0913
        self,
        *,
        selected: "AISelectedModel",
        messages: tuple[AIModelMessage, ...],
        tools: tuple["AIModelToolDefinition", ...],
        fallback_models: tuple["AISelectedModel", ...],
        tool_calling_requirement: Literal["required", "optional", "none"],
        loop_state: ToolLoopState,
        response_source: str,
        allow_context_recovery: bool,
    ) -> "_ToolLoopModelResult":
        attempts: list[ModelAttempt] = []
        last_finish_reason = "model_error"
        messages_for_call = messages
        recovered_messages_active = False

        for candidate in (selected, *fallback_models):
            while True:
                try:
                    response = await self._model_gateway.generate_native(
                        selected=candidate,
                        messages=messages_for_call,
                        tools=tools,
                        requirements=AIModelCallRequirements(
                            tool_calling=(
                                tool_calling_requirement if tools else "none"
                            ),
                        ),
                    )
                except AIModelCapabilityPlanningError as exc:
                    diagnostic = sanitize_model_diagnostic(str(exc))
                    attempts.append(
                        ModelAttempt(
                            attempt_index=loop_state.next_model_attempt_index(),
                            model_ref=model_ref(candidate),
                            status="failed",
                            response_source=response_source,
                            reason="capability_unavailable",
                            diagnostic=diagnostic,
                        )
                    )
                    last_finish_reason = "capability_unavailable"
                    break
                except Exception as exc:  # noqa: BLE001
                    diagnostic = sanitize_model_diagnostic(str(exc))
                    is_context_pressure = is_context_pressure_error(diagnostic)
                    observation = (
                        None
                        if is_context_pressure
                        else classify_capability_mismatch(
                            exc,
                            planned_feature=_planned_feature_for_tool_loop(
                                tools=tools,
                                tool_calling_requirement=tool_calling_requirement,
                                messages=messages_for_call,
                            ),
                            model_ref=model_ref(candidate),
                        )
                    )
                    attempts.append(
                        ModelAttempt(
                            attempt_index=loop_state.next_model_attempt_index(),
                            model_ref=model_ref(candidate),
                            status="failed",
                            response_source=response_source,
                            reason=(
                                "context_pressure"
                                if is_context_pressure
                                else (
                                    "capability_mismatch"
                                    if observation is not None
                                    else "model_error"
                                )
                            ),
                            diagnostic=diagnostic,
                            capability_observation=observation,
                        )
                    )
                    last_finish_reason = (
                        "context_pressure"
                        if is_context_pressure
                        else (
                            "capability_mismatch"
                            if observation is not None
                            else "model_error"
                        )
                    )
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
                    attempts.append(
                        ModelAttempt(
                            attempt_index=loop_state.next_model_attempt_index(),
                            model_ref=model_ref(candidate),
                            status="failed",
                            response_source=response_source,
                            reason="empty_response",
                        )
                    )
                    last_finish_reason = "empty_response"
                    if recovered_messages_active:
                        loop_state.context_recovery_failed = True
                    break

                attempts.append(
                    ModelAttempt(
                        attempt_index=loop_state.next_model_attempt_index(),
                        model_ref=model_ref(candidate),
                        status="success",
                        response_source=response_source,
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

    async def _finalize_after_max_rounds(
        self,
        *,
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
            selected=selected,
            messages=finalization_messages,
            tools=(),
            fallback_models=fallback_models,
            tool_calling_requirement=tool_calling_requirement,
            loop_state=loop_state,
            response_source="tool_loop_finalization",
            allow_context_recovery=False,
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


tool_gateway = ToolGateway()
