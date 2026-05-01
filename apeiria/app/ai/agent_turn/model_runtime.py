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

    def __init__(self, *, model_gateway: Any | None = None) -> None:
        if model_gateway is None:
            from apeiria.ai.model import model_gateway as default_model_gateway

            model_gateway = default_model_gateway
        self._model_gateway = model_gateway

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
                response = await self._model_gateway.generate_native(
                    selected=selected,
                    prompt=request.prompt,
                    messages=request.messages,
                    tools=request.tools,
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


def _completed_finish_reason(response_source: str) -> str:
    if response_source == "direct":
        return "direct_model_completed"
    return f"{response_source}_model_completed"


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
