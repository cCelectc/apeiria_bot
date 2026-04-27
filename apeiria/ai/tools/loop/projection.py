"""Projection helpers for tool-loop results and attempt diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelToolCall
    from apeiria.ai.tools.models import AIToolObservationResult

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


def project_tool_results(
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


def completed_observations(
    observations: list["AIToolObservationResult | None"],
) -> list["AIToolObservationResult"]:
    return [observation for observation in observations if observation is not None]


def summarize_arguments(arguments: Any) -> str:
    if not arguments:
        return "{}"
    text = str(arguments)
    if len(text) <= ARGUMENT_SUMMARY_CHAR_LIMIT:
        return text
    return f"{text[: ARGUMENT_SUMMARY_CHAR_LIMIT - 3].rstrip()}..."
