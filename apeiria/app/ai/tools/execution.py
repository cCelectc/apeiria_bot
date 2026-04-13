"""Pure helpers for capability execution outcomes."""

from __future__ import annotations

from typing import Any

from apeiria.app.ai.tools.models import (
    AICapabilityInvokeObservationOutput,
    AINoneBotCapabilityRequest,
    AIToolObservationResult,
)


def build_capability_success_result(
    request: AINoneBotCapabilityRequest,
    result: Any,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_observation(request.capability_name, result),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result=result,
        ),
    )


def build_capability_error_result(
    request: AINoneBotCapabilityRequest,
    error_message: str,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_error(request.capability_name, error_message),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result={"error": error_message},
        ),
        status="error",
    )


def build_capability_timeout_result(
    request: AINoneBotCapabilityRequest,
    timeout_seconds: float,
) -> AIToolObservationResult:
    return AIToolObservationResult(
        tool_name="plugin.capability",
        summary=_format_capability_timeout(
            request.capability_name,
            timeout_seconds,
        ),
        input_payload=request,
        output_payload=AICapabilityInvokeObservationOutput(
            capability_name=request.capability_name,
            result={
                "error": "timeout",
                "timeout_seconds": timeout_seconds,
            },
        ),
        status="timeout",
    )


def _format_capability_observation(
    capability_name: str,
    result: Any,
) -> str:
    if isinstance(result, dict):
        summary = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
        return f"- [plugin.capability] {capability_name}: {summary}"
    return f"- [plugin.capability] {capability_name}: {result}"


def _format_capability_error(
    capability_name: str,
    error_message: str,
) -> str:
    return f"- [plugin.capability] {capability_name} failed: {error_message}"


def _format_capability_timeout(
    capability_name: str,
    timeout_seconds: float,
) -> str:
    return (
        f"- [plugin.capability] {capability_name} timed out after "
        f"{timeout_seconds:.1f}s"
    )
