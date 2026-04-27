"""Shared AI turn attempt records used across model and tool boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelGenerateResponse, AISelectedModel


ModelAttemptStatus = Literal["success", "failed"]
ToolAttemptStatus = Literal["success", "error", "timeout", "skipped"]


@dataclass(frozen=True)
class PromptSafeObservation:
    """Tool observation content after applying the model-visible budget."""

    content: str
    truncated: bool = False
    original_length: int = 0


@dataclass(frozen=True)
class ModelAttempt:
    """One model invocation attempt inside an AI turn."""

    attempt_index: int
    model_ref: str
    status: ModelAttemptStatus
    response_source: str
    reason: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class ToolAttempt:
    """One requested tool call and its model-visible observation."""

    tool_call_id: str
    tool_name: str
    status: ToolAttemptStatus
    arguments_summary: str
    observation: PromptSafeObservation
    repetition_count: int = 1
    repeated: bool = False
    diagnostic: str | None = None
    native_observation: Any = None


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
            data["tool_loop_chain_repair_placeholders"] = (
                self.chain_repair_placeholders
            )
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
        return data


def model_ref(selected: "AISelectedModel") -> str:
    """Build a stable source:model display reference for attempt records."""

    model_name = str(selected.resolved_model_name or "").strip() or "?"
    return f"{selected.source.source_id}:{model_name}"


def sanitize_model_diagnostic(message: str) -> str:
    """Remove obvious credential material from model diagnostics."""

    sanitized = _SECRET_ASSIGNMENT_RE.sub(r"\1\2<redacted>", message)
    sanitized = _BEARER_RE.sub("Bearer <redacted>", sanitized)
    return sanitized or "model request failed"


def is_empty_model_response(response: "AIModelGenerateResponse | None") -> bool:
    """Return whether a provider response has no useful content or tool calls."""

    if response is None:
        return True
    return not response.content.strip() and not response.tool_calls


_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|authorization)(\s*=\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
