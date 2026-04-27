"""Turn-scoped model invocation helpers."""

from __future__ import annotations

from typing import Any

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
            except Exception as exc:  # noqa: BLE001
                diagnostic = sanitize_model_diagnostic(str(exc))
                attempts.append(
                    ModelAttempt(
                        attempt_index=index,
                        model_ref=model_ref(selected),
                        status="failed",
                        response_source=request.response_source,
                        reason="model_error",
                        diagnostic=diagnostic,
                    )
                )
                last_finish_reason = "model_error"
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
