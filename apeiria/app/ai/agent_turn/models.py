"""Value objects for one AI agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from apeiria.ai.turn_records import (  # noqa: TC001
    ModelAttempt,
    ToolAttempt,
)

if TYPE_CHECKING:
    from apeiria.ai.model import (
        AIModelGenerateResponse,
        AIModelMessage,
        AIModelToolDefinition,
        AISelectedModel,
    )


AgentTurnStatus = Literal["completed", "skipped", "failed", "interrupted"]


@dataclass(frozen=True)
class AgentTurnResult:
    """Structured final outcome for one AI runtime turn."""

    trace_id: str
    runtime_mode: str
    status: AgentTurnStatus
    finish_reason: str
    model_attempts: tuple[ModelAttempt, ...] = ()
    tool_attempts: tuple[ToolAttempt, ...] = ()
    response: "AIModelGenerateResponse | None" = None
    response_source: str | None = None
    diagnostic: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def skipped(
        cls,
        *,
        trace_id: str,
        runtime_mode: str,
        finish_reason: str,
        diagnostic: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AgentTurnResult":
        """Build a turn outcome for a pre-generation strategy skip."""

        return cls(
            trace_id=trace_id,
            runtime_mode=runtime_mode,
            status="skipped",
            finish_reason=finish_reason,
            diagnostic=diagnostic,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class AgentModelGenerationRequest:
    """Inputs for one turn-scoped model generation attempt chain."""

    trace_id: str
    session_id: str
    runtime_mode: str
    selected: "AISelectedModel"
    prompt: str = ""
    messages: tuple["AIModelMessage", ...] = ()
    tools: tuple["AIModelToolDefinition", ...] = ()
    response_source: str = "direct"
    fallback_models: tuple["AISelectedModel", ...] = ()


@dataclass(frozen=True)
class AgentModelGenerationResult:
    """Model generation result plus the corresponding turn outcome."""

    turn: AgentTurnResult
    response: "AIModelGenerateResponse | None"
    selected: "AISelectedModel | None" = None
