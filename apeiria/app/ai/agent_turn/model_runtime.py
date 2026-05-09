"""Turn-scoped model invocation helpers."""

from __future__ import annotations

from typing import Any

from apeiria.ai.model.runtime.capabilities import AIModelCapabilityPlanningError
from apeiria.ai.model.runtime.capability_sources import classify_capability_mismatch
from apeiria.ai.model.runtime.failures import classify_model_failure
from apeiria.ai.turn_records import (
    is_empty_model_response,
    model_ref,
    sanitize_model_diagnostic,
)
from apeiria.app.ai.agent_turn.models import (
    AgentModelGenerationRequest,
    AgentModelGenerationResult,
    AgentTurnResult,
    ModelAttempt,
)


class AgentTurnModelRuntime:
    """Run model attempts for one agent turn and record their outcomes."""

    def __init__(self, *, model_invoker: Any | None = None) -> None:
        if model_invoker is None:
            from apeiria.ai.model import model_invoker as default_model_invoker

            model_invoker = default_model_invoker
        self._model_invoker = model_invoker

    async def generate(
        self,
        request: AgentModelGenerationRequest,
    ) -> AgentModelGenerationResult:
        """Generate through the selected model and any provided fallbacks."""

        attempts: list[ModelAttempt] = []
        candidates = (request.selected, *request.fallback_models)
        last_finish_reason = "model_error"
        last_diagnostic: str | None = None

        for index, selected in enumerate(candidates, start=1):
            try:
                if request.stream_policy != "none" or request.stream_sink is not None:
                    response, stream_metadata = await self._generate_streamed_response(
                        request=request,
                        selected=selected,
                    )
                    if response is None:
                        _raise_empty_stream_response()
                    attempts.append(
                        ModelAttempt(
                            attempt_index=index,
                            model_ref=model_ref(selected),
                            status="success",
                            response_source=request.response_source,
                            reasoning_diagnostics=_reasoning_diagnostics(
                                response,
                                request=request,
                            ),
                        )
                    )
                    metadata = _turn_metadata_from_response(response)
                    if stream_metadata:
                        metadata = {
                            **metadata,
                            "streaming": stream_metadata,
                        }
                    return AgentModelGenerationResult(
                        response=response,
                        selected=selected,
                        turn=AgentTurnResult(
                            trace_id=request.trace_id,
                            runtime_mode=request.runtime_mode,
                            status="completed",
                            finish_reason=(
                                "direct_model_stream_completed"
                                if request.response_source == "direct"
                                else f"{request.response_source}_model_stream_completed"
                            ),
                            model_attempts=tuple(attempts),
                            response=response,
                            response_source=request.response_source,
                            metadata=metadata,
                        ),
                    )

                response = await self._model_invoker.generate_text(
                    selected=selected,
                    prompt=request.prompt,
                    messages=request.messages,
                    tools=request.tools,
                    options=request.reasoning_options,
                )
            except AIModelCapabilityPlanningError as exc:
                diagnostic = sanitize_model_diagnostic(str(exc))
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(selected),
                        status="failed",
                        response_source=request.response_source,
                        reason="capability_unavailable",
                        diagnostic=diagnostic,
                    )
                )
                last_finish_reason = "capability_unavailable"
                last_diagnostic = diagnostic
                continue
            except Exception as exc:  # noqa: BLE001
                diagnostic = sanitize_model_diagnostic(str(exc))
                reason = classify_model_failure(exc)
                observation = classify_capability_mismatch(
                    exc,
                    planned_feature=_planned_feature_for_request(request),
                    model_ref=model_ref(selected),
                )
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(selected),
                        status="failed",
                        response_source=request.response_source,
                        reason=reason,
                        diagnostic=diagnostic,
                        capability_observation=observation,
                    )
                )
                last_finish_reason = reason
                last_diagnostic = diagnostic
                continue

            if is_empty_model_response(response):
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(selected),
                        status="failed",
                        response_source=request.response_source,
                        reason="empty_response",
                    )
                )
                last_finish_reason = "empty_response"
                last_diagnostic = "model returned empty response"
                continue

            attempts.append(
                ModelAttempt(
                    attempt_index=index,
                    model_ref=model_ref(selected),
                    status="success",
                    response_source=request.response_source,
                    reasoning_diagnostics=_reasoning_diagnostics(
                        response,
                        request=request,
                    ),
                )
            )
            metadata = _turn_metadata_from_response(response)
            return AgentModelGenerationResult(
                response=response,
                selected=selected,
                turn=AgentTurnResult(
                    trace_id=request.trace_id,
                    runtime_mode=request.runtime_mode,
                    status="completed",
                    finish_reason=(
                        "fallback_model_completed"
                        if index > 1
                        else _completed_finish_reason(request.response_source)
                    ),
                    model_attempts=tuple(attempts),
                    response=response,
                    response_source=request.response_source,
                    metadata=metadata,
                ),
            )

        return AgentModelGenerationResult(
            response=None,
            selected=None,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="failed",
                finish_reason=last_finish_reason,
                model_attempts=tuple(attempts),
                diagnostic=last_diagnostic,
                response_source=request.response_source,
            ),
        )

    async def _generate_streamed_response(
        self,
        *,
        request: AgentModelGenerationRequest,
        selected: Any,
    ) -> tuple[Any | None, dict[str, object]]:
        stream_events: list[Any] = []
        stream_sink = request.stream_sink
        stream_iter = self._model_invoker.stream_text(
            selected=selected,
            prompt=request.prompt,
            messages=request.messages,
            tools=request.tools,
            options=request.reasoning_options,
        )
        async for event in stream_iter:
            stream_events.append(event)
            if stream_sink is not None:
                stream_sink(event)
            if getattr(event, "kind", None) == "final":
                response = getattr(event, "response", None)
                return response, _stream_metadata(stream_events, event)
        return None, _stream_metadata(stream_events, None)


def _completed_finish_reason(response_source: str) -> str:
    if response_source == "direct":
        return "direct_model_completed"
    return f"{response_source}_model_completed"


def _raise_empty_stream_response() -> None:
    raise RuntimeError("empty_stream_response")


def _planned_feature_for_request(request: AgentModelGenerationRequest) -> str:
    if request.tools:
        return "tool_calling"
    for message in request.messages:
        for part in getattr(message, "parts", ()):
            kind = getattr(part, "kind", None)
            if kind in {"image", "audio", "file"}:
                return "modality"
    return "unknown"


def _turn_metadata_from_response(response: Any) -> dict[str, object]:
    provider_data = getattr(response, "provider_data", None)
    if not isinstance(provider_data, dict):
        return {}
    raw_degradations = provider_data.get("apeiria_degradations")
    if not isinstance(raw_degradations, list):
        return {}

    degradations = [
        item
        for item in raw_degradations[:5]
        if isinstance(item, dict) and isinstance(item.get("kind"), str)
    ]
    if not degradations:
        return {}
    return {"capability_degradations": degradations}


def _reasoning_diagnostics(
    response: Any,
    *,
    request: AgentModelGenerationRequest,
) -> dict[str, object]:
    diagnostics = _reasoning_request_diagnostics(request)
    diagnostics.update(_reasoning_provider_diagnostics(response))
    if _has_provider_reasoning(response):
        diagnostics["provider_reasoning_present"] = True
    if diagnostics.get("requested_effort") and "degradation_reason" not in diagnostics:
        diagnostics["applied_effort"] = diagnostics["requested_effort"]
    return diagnostics


def _reasoning_request_diagnostics(
    request: AgentModelGenerationRequest,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    options = getattr(request.reasoning_options, "values", None)
    if isinstance(options, dict):
        requested_effort = options.get("reasoning_effort")
        if isinstance(requested_effort, str):
            diagnostics["requested_effort"] = requested_effort
            diagnostics["required"] = "reasoning_effort" in getattr(
                request.reasoning_options,
                "required",
                frozenset(),
            )
    return diagnostics


def _reasoning_provider_diagnostics(response: Any) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    provider_data = getattr(response, "provider_data", None)
    if not isinstance(provider_data, dict):
        return diagnostics
    for key in (
        "visible_reasoning_stripped",
        "stripped_reasoning_blocks",
    ):
        field = provider_data.get(key)
        if isinstance(field, bool | int):
            diagnostics[key] = field
    degradations = provider_data.get("apeiria_degradations")
    if isinstance(degradations, list):
        degradation_reason = _reasoning_degradation_reason(degradations)
        if degradation_reason is not None:
            diagnostics["degradation_reason"] = degradation_reason
    return diagnostics


def _reasoning_degradation_reason(degradations: list[object]) -> str | None:
    reasoning_degradation = next(
        (
            item
            for item in degradations
            if isinstance(item, dict) and item.get("kind") == "reasoning_omitted"
        ),
        None,
    )
    if not isinstance(reasoning_degradation, dict):
        return None
    reason = reasoning_degradation.get("reason")
    return reason if isinstance(reason, str) else None


def _has_provider_reasoning(response: Any) -> bool:
    return bool(
        getattr(response, "reasoning_content", None)
        or getattr(response, "reasoning_signature", None)
    )


def _stream_metadata(
    stream_events: list[Any],
    final_event: Any | None,
) -> dict[str, object]:
    if final_event is None:
        return {
            "status": "failed",
            "event_count": len(stream_events),
        }
    return {
        "status": "completed",
        "stream_id": getattr(final_event, "stream_id", None),
        "event_count": len(stream_events),
    }
