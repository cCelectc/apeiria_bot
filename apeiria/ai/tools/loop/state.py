"""Turn-local mutable state for one tool-loop invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.turn_records import ToolAttemptStatus


@dataclass
class ToolLoopState:
    """Mutable counters for one tool-loop invocation."""

    round_count: int = 0
    model_attempt_count: int = 0
    model_retry_count: int = 0
    context_recovery_attempted: bool = False
    context_recovery_succeeded: bool = False
    context_recovery_failed: bool = False
    context_recovery_compacted_messages: int = 0
    chain_repair_placeholders: int = 0
    chain_repair_orphans: int = 0
    consecutive_tool_error_rounds: int = 0
    max_consecutive_tool_error_rounds: int = 0
    finalization_attempted: bool = False
    finalization_succeeded: bool = False
    finalization_error: str | None = None
    finalization_ignored_tool_calls: int = 0
    capability_degradations: list[dict[str, Any]] = field(default_factory=list)
    repeated_tool_counts: dict[str, int] = field(default_factory=dict)

    def next_round(self) -> int:
        self.round_count += 1
        return self.round_count

    def next_model_attempt_index(self) -> int:
        self.model_attempt_count += 1
        return self.model_attempt_count

    def next_tool_repetition_count(self, tool_name: str) -> int:
        count = self.repeated_tool_counts.get(tool_name, 0) + 1
        self.repeated_tool_counts[tool_name] = count
        return count

    def record_tool_round(self, statuses: list[ToolAttemptStatus]) -> None:
        if statuses and all(status != "success" for status in statuses):
            self.consecutive_tool_error_rounds += 1
        else:
            self.consecutive_tool_error_rounds = 0
        self.max_consecutive_tool_error_rounds = max(
            self.max_consecutive_tool_error_rounds,
            self.consecutive_tool_error_rounds,
        )

    def can_attempt_context_recovery(self) -> bool:
        if self.context_recovery_attempted:
            return False
        self.context_recovery_attempted = True
        return True

    def metadata(self) -> dict[str, Any]:
        """Return compact metadata suitable for persisted assistant message meta."""

        data: dict[str, Any] = {
            "tool_loop_round_count": self.round_count,
            "tool_loop_model_attempt_count": self.model_attempt_count,
        }
        if self.model_retry_count:
            data["tool_loop_model_retry_count"] = self.model_retry_count
        if self.context_recovery_attempted:
            data["tool_loop_context_recovery_attempted"] = True
            data["tool_loop_context_recovery_succeeded"] = (
                self.context_recovery_succeeded
            )
            data["tool_loop_context_recovery_failed"] = self.context_recovery_failed
            data["tool_loop_context_recovery_compacted_messages"] = (
                self.context_recovery_compacted_messages
            )
        if self.chain_repair_placeholders or self.chain_repair_orphans:
            data["tool_loop_chain_repair_placeholders"] = self.chain_repair_placeholders
            data["tool_loop_chain_repair_orphans"] = self.chain_repair_orphans
        if self.max_consecutive_tool_error_rounds:
            data["tool_loop_max_consecutive_tool_error_rounds"] = (
                self.max_consecutive_tool_error_rounds
            )
        if self.finalization_attempted:
            data["tool_loop_finalization_attempted"] = True
            data["tool_loop_finalization_succeeded"] = self.finalization_succeeded
            if self.finalization_error:
                data["tool_loop_finalization_error"] = self.finalization_error
            if self.finalization_ignored_tool_calls:
                data["tool_loop_finalization_ignored_tool_calls"] = (
                    self.finalization_ignored_tool_calls
                )
        if self.capability_degradations:
            data["tool_loop_capability_degradations"] = self.capability_degradations
        return data
