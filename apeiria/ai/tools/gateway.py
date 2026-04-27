"""AI-internal tool gateway for reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.tools.function_calling import (
    build_function_tools,
    build_intents_from_tool_calls,
    function_name_to_tool_name,
)
from apeiria.ai.tools.models import (
    AIToolObservationRequest,
    AIToolObservationResult,
    AIToolPolicy,
)
from apeiria.ai.tools.policy import summarize_tool_policy
from apeiria.ai.turn_records import (
    ModelAttempt,
    PromptSafeObservation,
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

MAX_TOOL_ROUNDS = 3
DEFAULT_OBSERVATION_CHAR_LIMIT = 1200
DEFAULT_REPEATED_TOOL_THRESHOLD = 3
ARGUMENT_SUMMARY_CHAR_LIMIT = 160


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool call."""

    tool_call_id: str
    name: str
    summary: str
    ok: bool
    error: str | None = None
    native_observation: Any = None


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
        tool_results = _project_tool_results(tool_calls, observations)
        completed_observations = _completed_observations(observations)
        return ToolGatewayResult(
            policy_text=summarize_tool_policy(
                self._tool_service.registry.list_tools(),
                request.policy,
            ),
            result_lines=tuple(
                obs.summary if obs is not None else "- [tool] skipped: execution limit"
                for obs in observations
            ),
            turns=tuple(self._tool_service.build_tool_turns(completed_observations)),
            tool_results=tool_results,
            available_tools=(),
        )

    async def run_tool_loop(  # noqa: PLR0913
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
    ) -> ToolGatewayResult:
        all_result_lines: list[str] = []
        all_turns: list[AIToolTurnCreateInput] = []
        all_tool_results: list[ToolResult] = []
        all_model_attempts: list[ModelAttempt] = []
        all_tool_attempts: list[ToolAttempt] = []
        tool_message_history: list[AIModelMessage] = []
        final_response: AIModelGenerateResponse | None = None
        loop_finish_reason = "not_started"
        tool_repetition_counts: dict[str, int] = {}
        current_selected = selected

        for round_idx in range(max_rounds):
            current_messages = tuple(messages) + tuple(tool_message_history)

            model_result = await self._generate_tool_loop_model(
                selected=current_selected,
                messages=current_messages,
                tools=tools,
                fallback_models=_dedupe_fallbacks(
                    current_selected,
                    fallback_models,
                ),
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
            tool_results = _project_tool_results(response.tool_calls, observations)
            completed_observations = _completed_observations(observations)
            all_tool_results.extend(tool_results)
            all_turns.extend(
                self._tool_service.build_tool_turns(completed_observations)
            )

            obs_by_index = dict(enumerate(observations))
            for index, tool_call in enumerate(response.tool_calls):
                obs = obs_by_index.get(index)
                tool_name = (
                    intents[index].tool_name
                    if index < len(intents)
                    else function_name_to_tool_name(tool_call.name)
                )
                repetition_count = tool_repetition_counts.get(tool_name, 0) + 1
                tool_repetition_counts[tool_name] = repetition_count
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
                all_tool_attempts.append(
                    ToolAttempt(
                        tool_call_id=tool_call.tool_call_id,
                        tool_name=tool_name,
                        status=(obs.status if obs is not None else "skipped"),
                        arguments_summary=_summarize_arguments(tool_call.arguments),
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

            logger.debug(
                "Tool loop round {} completed: {} tool calls, {} observations",
                round_idx + 1,
                len(response.tool_calls),
                len(observations),
            )
        else:
            if final_response is not None and final_response.tool_calls:
                loop_finish_reason = "max_rounds_reached"

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

    async def _generate_tool_loop_model(
        self,
        *,
        selected: "AISelectedModel",
        messages: tuple[AIModelMessage, ...],
        tools: tuple["AIModelToolDefinition", ...],
        fallback_models: tuple["AISelectedModel", ...],
    ) -> "_ToolLoopModelResult":
        attempts: list[ModelAttempt] = []
        last_finish_reason = "model_error"

        for index, candidate in enumerate((selected, *fallback_models), start=1):
            try:
                response = await self._model_gateway.generate_native(
                    selected=candidate,
                    messages=messages,
                    tools=tools,
                )
            except Exception as exc:  # noqa: BLE001
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(candidate),
                        status="failed",
                        response_source="tool_loop",
                        reason="model_error",
                        diagnostic=sanitize_model_diagnostic(str(exc)),
                    )
                )
                last_finish_reason = "model_error"
                continue

            if is_empty_model_response(response):
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(candidate),
                        status="failed",
                        response_source="tool_loop",
                        reason="empty_response",
                    )
                )
                last_finish_reason = "empty_response"
                continue

            attempts.append(
                ModelAttempt(
                    attempt_index=index,
                    model_ref=model_ref(candidate),
                    status="success",
                    response_source="tool_loop",
                )
            )
            return _ToolLoopModelResult(
                response=response,
                selected=candidate,
                attempts=tuple(attempts),
                finish_reason="tool_loop_model_completed",
            )

        return _ToolLoopModelResult(
            response=None,
            selected=selected,
            attempts=tuple(attempts),
            finish_reason=last_finish_reason,
        )


@dataclass(frozen=True)
class _ToolLoopModelResult:
    response: "AIModelGenerateResponse | None"
    selected: "AISelectedModel"
    attempts: tuple[ModelAttempt, ...]
    finish_reason: str


def _project_tool_results(
    tool_calls: tuple["AIModelToolCall", ...],
    observations: list["AIToolObservationResult | None"],
) -> tuple[ToolResult, ...]:
    obs_by_index = dict(enumerate(observations))
    results: list[ToolResult] = []
    for index, call in enumerate(tool_calls):
        obs = obs_by_index.get(index)
        if obs is None:
            results.append(
                ToolResult(
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                    summary=f"- [{call.name}] skipped: execution limit",
                    ok=False,
                    error="skipped_execution_limit",
                )
            )
            continue
        results.append(
            ToolResult(
                tool_call_id=call.tool_call_id,
                name=call.name,
                summary=obs.summary,
                ok=obs.status == "success",
                error=None if obs.status == "success" else obs.status,
                native_observation=obs,
            )
        )
    return tuple(results)


def _completed_observations(
    observations: list["AIToolObservationResult | None"],
) -> list["AIToolObservationResult"]:
    return [observation for observation in observations if observation is not None]


def build_prompt_safe_observation(
    content: str,
    *,
    char_limit: int = DEFAULT_OBSERVATION_CHAR_LIMIT,
) -> PromptSafeObservation:
    """Return the model-visible preview for one tool observation."""

    normalized = str(content or "")
    original_length = len(normalized)
    if char_limit <= 0 or original_length <= char_limit:
        return PromptSafeObservation(
            content=normalized,
            truncated=False,
            original_length=original_length,
        )

    marker = "\n[truncated]"
    keep = max(char_limit - len(marker), 0)
    return PromptSafeObservation(
        content=f"{normalized[:keep].rstrip()}{marker}",
        truncated=True,
        original_length=original_length,
    )


def _summarize_arguments(arguments: Any) -> str:
    if not arguments:
        return "{}"
    text = str(arguments)
    if len(text) <= ARGUMENT_SUMMARY_CHAR_LIMIT:
        return text
    return f"{text[: ARGUMENT_SUMMARY_CHAR_LIMIT - 3].rstrip()}..."


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


tool_gateway = ToolGateway()
