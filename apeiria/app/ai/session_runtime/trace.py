"""Compact provider-neutral turn trace contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .strategy import RuntimeHardRuleAction  # noqa: TC001

if TYPE_CHECKING:
    from apeiria.ai.turn_records import ModelAttempt, ToolAttempt
    from apeiria.app.ai.agent_turn import AgentTurnResult
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.session_runtime.strategy import RuntimeHardRuleDecision


@dataclass(frozen=True, slots=True)
class TurnTrace:
    """Compact trace projection for one AI runtime turn."""

    trace_id: str
    session_id: str
    runtime_mode: str
    strategy_action: RuntimeHardRuleAction
    strategy_reason_codes: tuple[str, ...] = ()
    merged_message_count: int = 0
    merge_reason: str | None = None
    wait_reason: str | None = None
    defer_reason: str | None = None
    model_attempts: tuple["ModelAttempt", ...] = ()
    tool_attempts: tuple["ToolAttempt", ...] = ()
    final_response_source: str | None = None
    skip_reason: str | None = None
    delivery_status: str | None = None
    prompt_diagnostics: dict[str, object] | None = None

    def to_metadata(self) -> dict[str, object]:
        """Project the trace to compact metadata for diagnostics surfaces."""

        metadata: dict[str, object] = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "runtime_mode": self.runtime_mode,
            "strategy_action": self.strategy_action,
            "strategy_reason_codes": list(self.strategy_reason_codes),
            "merged_message_count": self.merged_message_count,
            "merge_reason": self.merge_reason,
            "wait_reason": self.wait_reason,
            "defer_reason": self.defer_reason,
            "model_attempt_count": len(self.model_attempts),
            "tool_attempt_count": len(self.tool_attempts),
            "tool_observation_count": len(self.tool_attempts),
            "final_response_source": self.final_response_source,
            "skip_reason": self.skip_reason,
            "delivery_status": self.delivery_status,
        }
        if self.prompt_diagnostics:
            metadata["prompt_diagnostics"] = self.prompt_diagnostics
        return metadata


def project_turn_trace(  # noqa: PLR0913
    *,
    session_id: str,
    strategy_decision: "RuntimeHardRuleDecision",
    turn_result: "AgentTurnResult | None",
    trace_id: str | None = None,
    runtime_mode: str | None = None,
    delivery_result: "DeliveryOutcome | None" = None,
) -> TurnTrace:
    """Project existing runtime attempt records into a compact turn trace."""

    resolved_trace_id = trace_id or (turn_result.trace_id if turn_result else "")
    resolved_runtime_mode = runtime_mode or (
        turn_result.runtime_mode if turn_result else "message"
    )
    skip_reason: str | None = None
    if turn_result is None:
        skip_reason = (
            strategy_decision.reason_codes[0]
            if strategy_decision.reason_codes
            else strategy_decision.action
        )
    elif turn_result.status == "skipped":
        skip_reason = turn_result.finish_reason

    return TurnTrace(
        trace_id=resolved_trace_id,
        session_id=session_id,
        runtime_mode=resolved_runtime_mode,
        strategy_action=strategy_decision.action,
        strategy_reason_codes=strategy_decision.reason_codes,
        merged_message_count=_int_evidence(strategy_decision, "merged_message_count"),
        merge_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "merge" and strategy_decision.reason_codes
            else None
        ),
        wait_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "wait" and strategy_decision.reason_codes
            else None
        ),
        defer_reason=(
            strategy_decision.reason_codes[0]
            if strategy_decision.action == "defer" and strategy_decision.reason_codes
            else None
        ),
        model_attempts=turn_result.model_attempts if turn_result else (),
        tool_attempts=turn_result.tool_attempts if turn_result else (),
        final_response_source=turn_result.response_source if turn_result else None,
        skip_reason=skip_reason,
        delivery_status=_delivery_status(delivery_result),
        prompt_diagnostics=(
            turn_result.metadata.get("prompt_diagnostics")
            if turn_result is not None
            and isinstance(turn_result.metadata.get("prompt_diagnostics"), dict)
            else None
        ),
    )


def _int_evidence(
    strategy_decision: "RuntimeHardRuleDecision",
    key: str,
) -> int:
    value = strategy_decision.evidence.get(key)
    return value if isinstance(value, int) else 0


def _delivery_status(delivery_result: "DeliveryOutcome | None") -> str:
    if delivery_result is None:
        return "not_required"
    return "delivered" if delivery_result.delivered else "failed"
