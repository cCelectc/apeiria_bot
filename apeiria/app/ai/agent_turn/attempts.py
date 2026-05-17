"""Shared model-attempt classification helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.capability_sources import classify_capability_mismatch
from apeiria.ai.model.runtime.failures import classify_model_failure
from apeiria.ai.turn_records import ModelAttempt, model_ref, sanitize_model_diagnostic

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.runtime.adapter import AIModelGenerateResponse
    from apeiria.ai.model.runtime.capabilities import (
        AIModelCallOptions,
        AIModelCapabilityPlanningError,
    )


def build_capability_failure_attempt(
    *,
    attempt_index: int,
    selected: "AISelectedModel",
    response_source: str,
    exc: "AIModelCapabilityPlanningError",
) -> ModelAttempt:
    """Build a standard attempt record for local capability-planning failures."""

    return ModelAttempt(
        attempt_index=attempt_index,
        model_ref=model_ref(selected),
        status="failed",
        response_source=response_source,
        reason="capability_unavailable",
        diagnostic=sanitize_model_diagnostic(str(exc)),
    )


def build_exception_failure_attempt(  # noqa: PLR0913
    *,
    attempt_index: int,
    selected: "AISelectedModel",
    response_source: str,
    exc: Exception,
    planned_feature: str,
    classify_capability: bool = True,
    reason: str | None = None,
) -> ModelAttempt:
    """Build a standard attempt record for provider/runtime invocation failures."""

    diagnostic = sanitize_model_diagnostic(str(exc))
    failure_reason = reason or classify_model_failure(exc)
    observation = (
        classify_capability_mismatch(
            exc,
            planned_feature=planned_feature,
            model_ref=model_ref(selected),
        )
        if classify_capability
        else None
    )
    return ModelAttempt(
        attempt_index=attempt_index,
        model_ref=model_ref(selected),
        status="failed",
        response_source=response_source,
        reason=failure_reason,
        diagnostic=diagnostic,
        capability_observation=observation,
    )


def build_empty_response_attempt(
    *,
    attempt_index: int,
    selected: "AISelectedModel",
    response_source: str,
) -> ModelAttempt:
    """Build a standard attempt record for empty provider responses."""

    return ModelAttempt(
        attempt_index=attempt_index,
        model_ref=model_ref(selected),
        status="failed",
        response_source=response_source,
        reason="empty_response",
    )


def build_success_attempt(
    *,
    attempt_index: int,
    selected: "AISelectedModel",
    response_source: str,
    response: "AIModelGenerateResponse",
    reasoning_options: "AIModelCallOptions | None",
) -> ModelAttempt:
    """Build a standard attempt record for successful model responses."""

    return ModelAttempt(
        attempt_index=attempt_index,
        model_ref=model_ref(selected),
        status="success",
        response_source=response_source,
        reasoning_diagnostics=build_reasoning_diagnostics(
            response,
            reasoning_options=reasoning_options,
        ),
    )


def build_reasoning_diagnostics(
    response: "AIModelGenerateResponse",
    *,
    reasoning_options: "AIModelCallOptions | None",
) -> dict[str, object]:
    """Return bounded reasoning diagnostics shared by model execution paths."""

    diagnostics: dict[str, object] = {}
    options = getattr(reasoning_options, "values", None)
    if isinstance(options, dict):
        requested_effort = options.get("reasoning_effort")
        if isinstance(requested_effort, str):
            diagnostics["requested_effort"] = requested_effort
            diagnostics["required"] = "reasoning_effort" in getattr(
                reasoning_options,
                "required",
                frozenset(),
            )
    provider_data = response.provider_data or {}
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
    if response.reasoning_content or response.reasoning_signature:
        diagnostics["provider_reasoning_present"] = True
    if diagnostics.get("requested_effort") and "degradation_reason" not in diagnostics:
        diagnostics["applied_effort"] = diagnostics["requested_effort"]
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


__all__ = [
    "build_capability_failure_attempt",
    "build_empty_response_attempt",
    "build_exception_failure_attempt",
    "build_reasoning_diagnostics",
    "build_success_attempt",
]
