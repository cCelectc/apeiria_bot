"""First-class AI tool runtime models."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime


class AIToolLevel(str, Enum):
    """Ordered AI tool permission levels."""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    HOST = "host"
    ADMIN = "admin"


_TOOL_LEVEL_ORDER: dict[AIToolLevel, int] = {
    AIToolLevel.NONE: 0,
    AIToolLevel.READ: 1,
    AIToolLevel.WRITE: 2,
    AIToolLevel.HOST: 3,
    AIToolLevel.ADMIN: 4,
}


def coerce_tool_level(value: AIToolLevel | str) -> AIToolLevel:
    """Return a tool level enum from a stored or API value."""

    if isinstance(value, AIToolLevel):
        return value
    return AIToolLevel(value)


def tool_level_allows(
    allowed: AIToolLevel | str,
    required: AIToolLevel | str,
) -> bool:
    """Return whether *allowed* grants *required* power."""

    return (
        _TOOL_LEVEL_ORDER[coerce_tool_level(allowed)]
        >= _TOOL_LEVEL_ORDER[coerce_tool_level(required)]
    )


AIToolOrigin = Literal["builtin", "plugin", "mcp"]
AIToolExecutionStatus = Literal[
    "success",
    "error",
    "timeout",
    "denied",
    "not_ready",
]
AIToolIntentKind = Literal[
    "observe_read_only",
    "invoke_tool",
    "manage_future_task",
    "update_memory",
]
AIToolReadinessCode = Literal[
    "ready",
    "disabled",
    "plugin_unavailable",
    "runtime_missing_capability",
    "missing_executor",
    "approval_missing",
]
AIToolExecutor = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class AIToolReadiness:
    """Readiness result for one tool in one runtime context."""

    ready: bool
    code: AIToolReadinessCode = "ready"
    reason: str = "ready"

    @classmethod
    def available(cls) -> "AIToolReadiness":
        return cls(ready=True)

    @classmethod
    def not_ready(
        cls,
        code: AIToolReadinessCode,
        reason: str,
    ) -> "AIToolReadiness":
        return cls(ready=False, code=code, reason=reason)


@dataclass(frozen=True)
class AIToolDefinition:
    """Provider-neutral AI-callable tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]
    required_level: AIToolLevel
    executor: AIToolExecutor | None
    readiness: AIToolReadiness = field(default_factory=AIToolReadiness.available)
    origin: AIToolOrigin = "builtin"
    enabled: bool = True
    manageable: bool = False
    version: int = 1
    tags: tuple[str, ...] = ()
    display_name: str | None = None

    @property
    def parameters(self) -> dict[str, Any]:
        """Alias used by model adapter projection."""

        return self.input_schema


@dataclass(frozen=True)
class AIToolPolicy:
    """Effective AI tool policy for one turn."""

    allowed_level: AIToolLevel = AIToolLevel.NONE


@dataclass(frozen=True)
class AIToolPolicyDecision:
    """Decision returned by tool policy evaluation."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class AIToolResult:
    """Unified return type for tool executors."""

    summary: str
    output_payload: Any = None
    status: AIToolExecutionStatus = "success"


@dataclass
class AIToolExecutionContext:
    """Unified context injected into every declarative tool executor."""

    session_id: str
    source_message_id: str | None
    trace_id: str | None
    message_text: str
    policy: AIToolPolicy
    recalled_memory_ids: tuple[str, ...]
    recalled_memory_contents: tuple[str, ...]
    relationship_context: str | None
    execution_timeout_seconds: float | None


@dataclass(frozen=True)
class AIToolExecutionView:
    """Pure persisted tool observation view."""

    execution_id: str
    session_id: str
    tool_name: str
    status: AIToolExecutionStatus
    input_json: str | None
    output_json: str | None
    created_at: datetime
    trace_id: str | None = None
    call_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AIToolIntent:
    """One planned tool action awaiting execution."""

    tool_name: str
    kind: AIToolIntentKind
    input_payload: Any
    reason: str | None = None
    call_id: str | None = None


@dataclass(frozen=True)
class AIToolIntentPreview:
    """One planned tool intent visible to admin preview surfaces."""

    tool_name: str
    kind: str
    reason: str | None
    input_payload: object | None


@dataclass(frozen=True)
class AIToolExecutionRequest:
    """Inputs for executing tool intents within one runtime turn."""

    session_id: str
    source_message_id: str | None
    trace_id: str | None
    message_text: str
    policy: AIToolPolicy
    recalled_memory_ids: tuple[str, ...]
    recalled_memory_contents: tuple[str, ...]
    relationship_context: str | None
    execution_timeout_seconds: float | None = None


@dataclass(frozen=True)
class AIMemoryQueryObservationInput:
    """Structured input payload for memory.query observations."""

    query_text: str


@dataclass(frozen=True)
class AIMemoryQueryObservationOutput:
    """Structured output payload for memory.query observations."""

    memory_ids: tuple[str, ...]


@dataclass(frozen=True)
class AIMemoryUpdateInput:
    """Structured input payload for memory.update operations."""

    memory_id: str
    updated_content: str
    salience: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class AIMemoryUpdateObservationOutput:
    """Structured output payload for memory.update operations."""

    memory_id: str
    content: str
    salience: float
    confidence: float


@dataclass(frozen=True)
class AIRelationshipInspectObservationOutput:
    """Structured output payload for relationship.inspect observations."""

    relationship_context: str


@dataclass(frozen=True)
class AIToolObservationResult:
    """One tool observation ready for prompt injection."""

    tool_name: str
    summary: str
    input_payload: Any
    output_payload: Any
    status: AIToolExecutionStatus = "success"
    reason: str | None = None
    call_id: str | None = None


@dataclass(frozen=True)
class AIToolTurnCreateInput:
    """One tool observation turn to be written into conversation context."""

    author_id: str
    text_content: str
    meta: dict[str, Any]

    @property
    def sender_id(self) -> str:
        return self.author_id

    @property
    def content_text(self) -> str:
        return self.text_content

    @property
    def raw_payload(self) -> dict[str, Any]:
        return self.meta
