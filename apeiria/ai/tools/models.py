"""Tool domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

AIToolRiskLevel = Literal["low", "medium", "high"]
AIToolOrigin = Literal["builtin", "plugin", "skill"]
AIToolIntentKind = Literal[
    "observe_read_only",
    "invoke_capability",
    "manage_future_task",
    "update_memory",
]
AIToolCapabilityMode = Literal["off", "private_only", "direct_only"]
AIToolExecutionStatus = Literal["success", "error", "timeout"]


@dataclass(frozen=True)
class AIToolSpec:
    """Declarative tool definition visible to the AI runtime layer.

    When ``entrypoint`` is provided, the tool can be executed generically
    without per-tool dispatch logic.  The ``parameters`` tuple describes
    the function signature for JSON Schema generation.
    """

    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    risk_level: AIToolRiskLevel = "low"
    is_capability_bridge: bool = False
    parameters: tuple[tuple[str, str, str, bool, tuple[str, ...] | None, Any], ...] = ()
    entrypoint: Callable[..., Awaitable[AIToolResult]] | None = None
    origin: AIToolOrigin = "builtin"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class AIToolResult:
    """Unified return type for declarative tool handlers."""

    summary: str
    output_payload: Any = None
    status: AIToolExecutionStatus = "success"


@dataclass
class AIToolExecutionContext:
    """Unified context injected into every declarative tool handler."""

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
class AIToolPolicy:
    """Pure tool access policy for one AI scene."""

    execution_enabled: bool = False
    allowed_tool_names: set[str] | None = None
    denied_tool_names: set[str] = field(default_factory=set)
    allow_high_risk_tools: bool = False
    allow_capability_bridge: bool = False


@dataclass(frozen=True)
class AIToolPolicyDecision:
    """Decision returned by tool policy evaluation."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class AINoneBotCapabilityRequest:
    """Structured request for a whitelist-based NoneBot capability bridge."""

    capability_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIToolExecutionView:
    """Pure execution record view."""

    execution_id: str
    session_id: str
    tool_name: str
    status: str
    input_json: str | None
    output_json: str | None
    created_at: datetime


@dataclass(frozen=True)
class AIToolIntent:
    """One planned tool action awaiting execution."""

    tool_name: str
    kind: AIToolIntentKind
    input_payload: Any
    reason: str | None = None


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
class AICapabilityInvokeObservationOutput:
    """Structured output payload for plugin.capability observations."""

    capability_name: str
    result: Any


@dataclass(frozen=True)
class AIPluginInspectCapabilityInput:
    """Structured input payload for plugin.inspect capability."""

    plugin_query: str


@dataclass(frozen=True)
class AIPluginInspectCapabilityOutput:
    """Structured output payload for plugin.inspect capability."""

    plugin_query: str
    plugin_name: str
    module_name: str
    description: str
    usage: str


@dataclass(frozen=True)
class AIToolObservationResult:
    """One read-only tool observation ready for prompt injection."""

    tool_name: str
    summary: str
    input_payload: Any
    output_payload: Any
    status: AIToolExecutionStatus = "success"


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
